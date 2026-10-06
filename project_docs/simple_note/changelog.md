# Changelog

All notable changes to `note`. Versions follow `MAJOR.MINOR.PATCH`; the version lives in the script
(`VERSION`) and is reported by `note --version`.

## Unreleased

### Added

- `note help [command]` — the help text reachable as a command instead of only as a flag:
  `note help` lists every command with its aliases, `note help rm` describes one command (aliases
  accepted), `note help whatever` prints the list and exits `1`. It short-circuits before config and
  index loading, so it creates no data directory and opens no editor.

## 0.1.1 — 2026-10-06

### Added

- `note recover` files drafts left behind by an interrupted run (killed process, lost power). Such
  drafts are invisible to search by design; `note where` now reports their count and points at both
  `note recover` (file them) and `note gc` (prune them).
- `note gc` prunes abandoned drafts as well as trash buckets: `-d/--days` (default 30) sets the age
  limit and `--all` removes every draft, in both cases with a one-hour floor so a draft that an open
  editor session is still using is never deleted.
- `note <words>` now starts a new note titled with those words (previously argparse exited `2` on the
  unrecognized command word). Only the first word is inspected, so `note --root X ls` still parses,
  and titles colliding with a command name need `note new <title>`.

### Fixed

- `--root` and `--editor` given *before* the subcommand were silently discarded by the sub-parser's
  own defaults, so `note --root /tmp/scratch ls` operated on the default root. Both positions now
  behave identically.
- `ls`/`find`/`tag --json` reported the indexed one-line snippet in the `body` field while
  `show --json` reported the full body. Note objects now always carry the full `body`, plus a
  separate `snippet` field for the display line.
- `note gc --all` printed "(older than 30d)" regardless of scope; it now says "(all trash)".
- `note tag <name> -p` was rejected by the argument parser even though the list/pick path supported
  printing (`ls`/`find` had `-p`; `tag` was missing it).

### Changed

- The index runs in SQLite WAL mode with a 10 s busy timeout and `synchronous=NORMAL`. Readers
  (pickers, listings, searches) no longer queue behind a concurrent writer: measured 0.07 s for
  `note ls` while another process held a write transaction, where the default rollback journal
  stalled the connection for up to 5 s.

## 0.1.0 — 2026-10-06

First release. `note` opens the editor on a new note that is already dated, timestamped, titled,
tagged and indexed by the time you quit.

### Added

- **Capture**: `note` / `note new` (editor flow with empty-draft discard and slug-from-edited-title),
  `note add` (arguments or stdin), `note append` (`--to REF`, `--bullet` for `- HH:MM` entries).
- **Search**: `note find` over an SQLite FTS5 index (title/body/tags, `bm25` weighted 8/1/3, prefix
  matching, substring fallback), filters `-t/--tag`, `--since`, `--until`, `--cwd`, `--host`,
  `--sort rank|date`, and `-e/--regex` via ripgrep.
- **Browse**: `note ls`, `note last`, `note open`, `note show` (raw or `--preview`), `note tags`,
  `note tag <name>` — all with fzf pickers and a metadata + body preview pane.
- **Manage**: `note rm` (trash with `.meta` pointers, `--purge` for permanent deletion),
  `note restore`, `note gc`, `note reindex`, `note where`.
- **Storage**: `notes/YYYY/MM/YYYY-MM-DD_HHMMSS-slug.md` with front matter recording id, title,
  created/updated timestamps, tags, cwd, host, git `branch@sha` and tmux session; inline `#hashtags`
  become tags.
- **Indexing**: derived SQLite FTS5 index resynced from file mtime/size on every command, so hand
  edits, renames and deletions are picked up without reindexing; `index.db` is disposable.
- **Scripting**: global `--json` and `-p/--print-path`, `-q/--quiet`, `--root`/`--editor` overrides,
  `$NOTE_HOME` / `$NOTE_EDITOR` / `$NOTE_NO_FZF` / `NO_COLOR`.
- **Degradation**: numbered picker without fzf, tokenized search without ripgrep, `$VISUAL`/`$EDITOR`
  fallback without nvim, atomic writes (`os.replace`) on every path that touches a note.
- **Tests**: 43 pytest cases (44 after the `snippet` case above) driving the real binary, including
  the real fzf picker on a pty.

### Known limitations at 0.1.0

- Linux/POSIX only; not exercised on macOS or Windows.
- The fzf multi-select plus delete-confirmation pair has been verified in parts rather than in one
  interactive session.
- Local and single-user: no sync, multi-device or encryption.
