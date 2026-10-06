"""Tests for the `note` CLI. Run with: pytest -q (or: make test)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "note"
FAKE_EDITOR = """#!/bin/sh
# Stands in for nvim: logs the argv, appends $FAKE_BODY to the draft, optionally retitles it.
p="$1"
[ -n "$EDITOR_LOG" ] && echo "$@" >> "$EDITOR_LOG"
[ -n "$FAKE_DELETE" ] && rm -f "$p" && exit 0
[ -n "$FAKE_CLEAR" ] && : > "$p"
[ -n "$FAKE_TITLE" ] && sed -i "s|^title: .*|title: $FAKE_TITLE|" "$p"
[ -n "$FAKE_BODY" ] && printf '\\n%s\\n' "$FAKE_BODY" >> "$p"
exit 0
"""


@pytest.fixture(scope="session")
def note_mod():
    loader = importlib.machinery.SourceFileLoader("note_cli", str(SCRIPT))
    spec = importlib.util.spec_from_loader("note_cli", loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["note_cli"] = mod
    loader.exec_module(mod)
    return mod


@pytest.fixture
def env(tmp_path):
    editor = tmp_path / "fake-editor"
    editor.write_text(FAKE_EDITOR)
    editor.chmod(0o755)
    e = dict(os.environ)
    e.update(
        NOTE_HOME=str(tmp_path / "data"),
        XDG_CONFIG_HOME=str(tmp_path / "cfg"),
        NOTE_EDITOR=str(editor),
        NOTE_NO_FZF="1",
        NO_COLOR="1",
    )
    for key in ("EDITOR", "VISUAL", "NOTE_HOME_OVERRIDE"):
        e.pop(key, None)
    return e


def run(env, *args, stdin=None, cwd=None, extra_env=None):
    e = dict(env)
    e.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
        env=e,
        cwd=cwd or ROOT,
        timeout=60,
    )


def run_in_pty(env, argv, timeout=25):
    """Run with a pty on stdin/stdout so the CLI takes its interactive path."""
    import fcntl
    import pty
    import select
    import signal
    import struct
    import termios
    import time

    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
    proc = subprocess.Popen(argv, stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
    os.close(slave)
    out, start = b"", time.time()
    while time.time() - start < timeout:
        if select.select([master], [], [], 0.3)[0]:
            try:
                chunk = os.read(master, 65536)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
        if proc.poll() is not None:
            break
    if proc.poll() is None:
        proc.send_signal(signal.SIGKILL)
    proc.wait(timeout=5)
    os.close(master)
    return proc.returncode, out.decode(errors="replace")


def notes_of(env, tmp_path) -> list[Path]:
    return sorted((tmp_path / "data" / "notes").rglob("*.md"))


def frontmatter_of(path: Path) -> dict:
    text = path.read_text()
    assert text.startswith("---\n"), f"no front matter in {path}"
    block = text.split("---\n", 2)[1]
    meta = {}
    for line in block.strip().splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip().strip('"')
    return meta


# --------------------------------------------------------------------------- units


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Fixed the flaky CI test!", "fixed-the-flaky-ci-test"),
        ("  spaces   and---dashes  ", "spaces-and-dashes"),
        ("café ünïcode notes", "cafe-unicode-notes"),
        ("", "note"),
        ("###", "note"),
        ("one two three four five six seven eight", "one-two-three-four-five-six"),
    ],
)
def test_slugify(note_mod, text, expected):
    assert note_mod.slugify(text) == expected


def test_frontmatter_roundtrip(note_mod):
    meta = {"id": "x", "title": "a: b", "tags": ["one", "two"], "cwd": "/tmp/some dir", "session": ""}
    text = note_mod.dump_frontmatter(meta) + "\nbody line\n"
    parsed, body = note_mod.parse_frontmatter(text)
    assert parsed == {"id": "x", "title": "a: b", "tags": ["one", "two"], "cwd": "/tmp/some dir"}
    assert body == "body line\n"


def test_frontmatter_tolerates_hand_edits(note_mod):
    parsed, body = note_mod.parse_frontmatter("---\ntags:\n  - alpha\n  - beta\ncustom: kept\n---\nhi\n")
    assert parsed["tags"] == ["alpha", "beta"]
    assert parsed["custom"] == "kept"
    assert body == "hi\n"
    # a plain markdown file with no front matter is left alone
    parsed, body = note_mod.parse_frontmatter("# just markdown\n")
    assert parsed == {} and body == "# just markdown\n"


@pytest.mark.parametrize(
    "spec,kind",
    [("today", "day"), ("2026-01-02", "day"), ("2026-01-02T10:30:00", "exact"), ("-7d", "day")],
)
def test_parse_when(note_mod, spec, kind):
    got = note_mod.parse_when(spec)
    assert isinstance(got, datetime)
    if kind == "day":
        assert (got.hour, got.minute, got.second) == (0, 0, 0)
    assert got < datetime.now(got.tzinfo)


def test_parse_when_rejects_garbage(note_mod):
    with pytest.raises(SystemExit):
        note_mod.parse_when("last tuesday-ish")


# --------------------------------------------------------------------------- capture


def test_add_writes_dated_file_with_context(env, tmp_path):
    r = run(env, "add", "Deploy checklist for the api", "-t", "ops,deploy", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    files = notes_of(env, tmp_path)
    assert len(files) == 1
    name = files[0].name
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{6}-deploy-checklist-for-the-api\.md", name), name
    assert files[0].parent.name == f"{datetime.now():%m}"  # notes/YYYY/MM/
    meta = frontmatter_of(files[0])
    assert meta["title"] == "Deploy checklist for the api"
    assert meta["tags"] == "[ops, deploy]"
    assert meta["cwd"] == str(tmp_path)
    assert meta["host"] and meta["id"].startswith(f"{datetime.now():%Y%m%d}")
    assert json.loads(run(env, "where", "--json").stdout)["notes_count"] == 1


def test_add_multiline_from_stdin_splits_title_and_body(env, tmp_path):
    r = run(env, "add", stdin="Ledger design\nUse an append-only log.\nsecond line\n")
    assert r.returncode == 0, r.stderr
    text = notes_of(env, tmp_path)[0].read_text()
    assert "title: Ledger design" in text
    assert text.endswith("Use an append-only log.\nsecond line\n")


def test_hashtags_in_body_become_tags(env, tmp_path):
    run(env, "add", "Kafka compaction #arch #kafka", cwd=tmp_path)
    meta = frontmatter_of(notes_of(env, tmp_path)[0])
    assert meta["tags"] == "[arch, kafka]"
    assert json.loads(run(env, "tags", "--json").stdout) == {"arch": 1, "kafka": 1}


def test_editor_flow_slugs_after_edited_title(env, tmp_path):
    r = run(env, "new", cwd=tmp_path, extra_env={"FAKE_BODY": "fixed the flaky test #ci", "FAKE_TITLE": "Flaky CI test fix"})
    assert r.returncode == 0, r.stderr
    files = notes_of(env, tmp_path)
    assert len(files) == 1
    assert files[0].name.endswith("-flaky-ci-test-fix.md")
    meta = frontmatter_of(files[0])
    assert meta["title"] == "Flaky CI test fix" and meta["tags"] == "[ci]"
    assert "fixed the flaky test" in files[0].read_text()
    assert list((tmp_path / "data" / ".tmp").iterdir()) == []  # draft cleaned up
    assert "note: saved" in r.stderr + r.stdout


def test_empty_editor_session_discards_note(env, tmp_path):
    r = run(env, "new", cwd=tmp_path, extra_env={"FAKE_CLEAR": "1"})
    assert r.returncode == 0
    assert notes_of(env, tmp_path) == []
    assert list((tmp_path / "data" / ".tmp").iterdir()) == []
    assert json.loads(run(env, "where", "--json").stdout)["notes_count"] == 0


def test_add_requires_text(env):
    r = run(env, "add", stdin="")
    assert r.returncode == 1 and "nothing to add" in r.stderr


def test_append_targets_newest_note(env, tmp_path):
    run(env, "add", "alpha note")
    run(env, "add", "zulu note")
    r = run(env, "append", "--bullet", "follow up on zulu")
    assert r.returncode == 0, r.stderr
    assert "zulu-note" in r.stdout
    zulu = next(p for p in notes_of(env, tmp_path) if "zulu" in p.name)
    alpha = next(p for p in notes_of(env, tmp_path) if "alpha" in p.name)
    assert re.search(r"- \d\d:\d\d follow up on zulu", zulu.read_text())
    assert "follow up" not in alpha.read_text()


def test_append_to_named_note_by_basename_and_uid(env, tmp_path):
    run(env, "add", "alpha note")
    run(env, "add", "zulu note")
    alpha = next(p for p in notes_of(env, tmp_path) if "alpha" in p.name)
    uid = frontmatter_of(alpha)["id"]
    assert run(env, "append", "--to", alpha.name, "via basename").returncode == 0
    assert run(env, "append", "--to", uid, "via uid").returncode == 0
    body = alpha.read_text()
    assert "via basename" in body and "via uid" in body


def test_append_without_notes_fails(env):
    r = run(env, "append", "orphan")
    assert r.returncode == 1 and "no notes yet" in r.stderr


# --------------------------------------------------------------------------- index


def test_sync_picks_up_external_edits_and_deletions(env, tmp_path):
    run(env, "add", "sync me")
    path = notes_of(env, tmp_path)[0]
    assert json.loads(run(env, "find", "sync", "--json").stdout)[0]["body"] == ""

    path.write_text(path.read_text() + "\nexternally appended sentence\n")
    hits = json.loads(run(env, "find", "externally", "--json").stdout)
    assert len(hits) == 1 and "externally appended" in hits[0]["body"]

    path.unlink()
    assert run(env, "find", "sync", "-p").stdout.strip() == ""
    assert json.loads(run(env, "where", "--json").stdout)["notes_count"] == 0


def test_reindex_rebuilds_deleted_index(env, tmp_path):
    run(env, "add", "survives reindex")
    (tmp_path / "data" / "index.db").unlink()
    r = run(env, "reindex")
    assert r.returncode == 0 and "1 note(s)" in r.stdout
    assert json.loads(run(env, "find", "reindex", "--json").stdout)


def test_show_prints_frontmatter_and_accepts_fragments(env, tmp_path):
    run(env, "add", "rendered note")
    path = notes_of(env, tmp_path)[0]
    by_fragment = run(env, "show", path.stem.split("-", 3)[-1])
    by_prefix = run(env, "show", path.stem[:16])
    by_uid = run(env, "show", frontmatter_of(path)["id"])
    for r in (by_fragment, by_prefix, by_uid):
        assert r.returncode == 0 and "rendered note" in r.stdout


def test_show_missing_note_fails(env):
    r = run(env, "show", "does-not-exist")
    assert r.returncode == 1 and "no note matching" in r.stderr


def test_show_accepts_literal_paths_and_preview_form(env, tmp_path):
    run(env, "add", "preview me #demo", cwd=tmp_path)
    path = notes_of(env, tmp_path)[0]
    raw = run(env, "show", "--", str(path))
    assert raw.returncode == 0 and raw.stdout.startswith("---\n")
    preview = run(env, "show", "--preview", "--", str(path))
    assert preview.returncode == 0
    assert preview.stdout.splitlines()[0].startswith("preview me")
    assert "#demo" in preview.stdout and not preview.stdout.startswith("---")


# --------------------------------------------------------------------------- search


@pytest.fixture
def seeded(env, tmp_path):
    run(env, "add", "Kafka compaction strategy", "-t", "arch")
    run(env, "add", "Pytest fixture teardown notes", "-t", "python")
    run(env, "add", "Kafka rebalance storm", "-t", "arch,python")
    return env, tmp_path


def test_find_matches_title_and_body(env, tmp_path):
    run(env, "add", "searchable title")
    run(env, "add", "other note with needle-in-haystack body")
    titles = [n["title"] for n in json.loads(run(env, "find", "needle", "--json").stdout)]
    assert titles == ["other note with needle-in-haystack body"]
    assert [n["title"] for n in json.loads(run(env, "find", "searchable", "--json").stdout)] == ["searchable title"]


def test_find_substring_fallback_for_punctuation(env, tmp_path):
    run(env, "add", "punctuation case: x-y?z!")
    # tokens survive FTS tokenization, so the plain path already matches
    assert len(json.loads(run(env, "find", "x-y?z", "--json").stdout)) == 1
    # a query that tokenizes to nothing falls back to a substring scan
    assert len(json.loads(run(env, "find", "y?z", "--json").stdout)) == 1
    assert len(json.loads(run(env, "find", "compaction", "--json").stdout)) == 0


def test_find_tag_and_date_filters(seeded):
    env, _ = seeded
    arch = json.loads(run(env, "find", "-t", "arch", "--json").stdout)
    assert {n["title"] for n in arch} == {"Kafka compaction strategy", "Kafka rebalance storm"}
    assert len(json.loads(run(env, "find", "-t", "arch", "-t", "python", "--json").stdout)) == 1
    assert json.loads(run(env, "find", "kafka", "--since", "today", "--json").stdout)
    assert json.loads(run(env, "find", "kafka", "--since", "-1d", "--json").stdout)
    assert json.loads(run(env, "find", "kafka", "--until", "today", "--json").stdout)  # today is inclusive
    assert json.loads(run(env, "find", "kafka", "--until", "-1d", "--json").stdout) == []
    assert run(env, "find", "kafka", "--until", "-1d").returncode == 1


def test_find_ordering_by_date(seeded):
    env, _ = seeded
    titles = [n["title"] for n in json.loads(run(env, "find", "kafka", "--sort", "date", "--json").stdout)]
    assert titles == ["Kafka rebalance storm", "Kafka compaction strategy"]


def test_find_requires_a_query_or_filter(env):
    r = run(env, "find")
    assert r.returncode == 1 and "give a search query" in r.stderr


def test_find_regex_uses_ripgrep(seeded):
    env, _ = seeded
    out = json.loads(run(env, "find", "--regex", r"rebalance\s+storm", "--json").stdout)
    assert [n["title"] for n in out] == ["Kafka rebalance storm"]


def test_ls_lists_newest_first_and_reports_paths(seeded, tmp_path):
    env, _ = seeded
    rows = json.loads(run(env, "ls", "--json").stdout)
    assert [n["title"] for n in rows] == ["Kafka rebalance storm", "Pytest fixture teardown notes", "Kafka compaction strategy"]
    printed = run(env, "ls", "-p").stdout
    first_line = printed.splitlines()[0]
    assert "Kafka rebalance storm" in first_line
    assert first_line.split()[-1].endswith("-kafka-rebalance-storm.md")


def test_tag_command_lists_and_filters(env, tmp_path):
    run(env, "add", "one #arch")
    run(env, "add", "two #python")
    assert json.loads(run(env, "tags", "--json").stdout) == {"arch": 1, "python": 1}
    picked = json.loads(run(env, "tag", "#arch", "--json").stdout)
    assert [n["title"] for n in picked] == ["one"]
    assert run(env, "tag", "missing").returncode == 1
    # same scripting flags as ls/find
    printed = run(env, "tag", "arch", "-p")
    assert printed.returncode == 0 and printed.stdout.split()[-1].endswith("-one.md")
    assert run(env, "tag", "arch", "-n", "1", "-p").stdout.count("\n") == 1


# --------------------------------------------------------------------------- delete


def test_rm_requires_confirmation_and_moves_to_trash(env, tmp_path):
    run(env, "add", "delete me")
    run(env, "add", "keep me")
    aborted = run(env, "rm", "delete", "-a", stdin="n\n")
    assert aborted.returncode == 1 and len(notes_of(env, tmp_path)) == 2

    ok = run(env, "rm", "delete", "-a", stdin="y\n")
    assert ok.returncode == 0
    assert [p.name for p in notes_of(env, tmp_path)] == [p.name for p in notes_of(env, tmp_path) if "keep" in p.name]
    trashed = list((tmp_path / "data" / "trash").rglob("*.md"))
    assert len(trashed) == 1 and "delete-me" in trashed[0].name
    assert trashed[0].with_name(trashed[0].name + ".meta").is_file()
    assert json.loads(run(env, "where", "--json").stdout)["notes_count"] == 1
    assert run(env, "find", "delete", "-p").stdout.strip() == ""


def test_rm_purge_skips_trash(env, tmp_path):
    run(env, "add", "gone forever")
    assert run(env, "rm", "gone", "-a", "-y", "--purge").returncode == 0
    assert notes_of(env, tmp_path) == []
    assert list((tmp_path / "data" / "trash").rglob("*.md")) == []


def test_rm_refuses_without_tty_or_yes(env, tmp_path):
    run(env, "add", "protected note")
    r = run(env, "rm", "protected", "-a", stdin="")
    assert r.returncode == 1 and "aborted" in r.stderr
    assert len(notes_of(env, tmp_path)) == 1


def test_restore_brings_notes_back(env, tmp_path):
    run(env, "add", "restore me")
    run(env, "rm", "restore", "-a", stdin="y\n")
    assert notes_of(env, tmp_path) == []
    r = run(env, "restore", "-a")
    assert r.returncode == 0 and "restored" in r.stdout
    files = notes_of(env, tmp_path)
    assert len(files) == 1 and "restore-me" in files[0].name
    assert "restore me" in files[0].read_text()
    assert json.loads(run(env, "where", "--json").stdout)["notes_count"] == 1


def test_gc_purges_trash(env, tmp_path):
    run(env, "add", "gc me")
    run(env, "rm", "gc", "-a", stdin="y\n")
    assert run(env, "gc", "--all").returncode == 0
    assert list((tmp_path / "data" / "trash").rglob("*")) in ([], [tmp_path / "data" / "trash"])


def test_last_show_returns_newest(env, tmp_path):
    run(env, "add", "first note")
    run(env, "add", "second note")
    r = run(env, "last", "--show")
    assert r.returncode == 0 and "second note" in r.stdout


def test_editor_command_is_nvim_plus_position(env, tmp_path, monkeypatch, note_mod):
    cfg = note_mod.load_config(str(tmp_path / "data"), None)
    assert cfg.editor, "editor must resolve"
    cfg.editor = ["nvim"]
    calls = []

    def fake_call(cmd, *a, **kw):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(note_mod.subprocess, "call", fake_call)
    note_mod.open_in_editor(cfg, tmp_path / "x.md")
    assert calls == [["nvim", "+", str(tmp_path / "x.md")]]


# --------------------------------------------------------------------------- fzf integration


@pytest.mark.skipif(shutil.which("fzf") is None, reason="fzf is not installed")
def test_fzf_picker_opens_the_selected_note(env, tmp_path):
    """Full interactive path: real fzf picker -> tab-delimited selection -> editor.

    fzf runs with --select-1 so a single match is chosen without typing, which keeps the test
    deterministic while still exercising the real fzf subprocess and its output parsing.
    """
    config_dir = tmp_path / "cfg" / "note"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text('fzf_opts = "--height=90% --select-1 --exit-0 --no-sort"\n')
    editor_log = tmp_path / "editor.log"
    interactive = dict(env, EDITOR_LOG=str(editor_log))
    interactive.pop("NOTE_NO_FZF", None)

    run(interactive, "add", "Kafka compaction strategy")
    run(interactive, "add", "Rebalance storm postmortem")
    assert not editor_log.exists()

    rc, screen = run_in_pty(interactive, [sys.executable, str(SCRIPT), "find", "compaction"])
    assert rc == 0, screen[-800:]
    opened = editor_log.read_text().strip()
    assert opened.endswith("-kafka-compaction-strategy.md"), opened
