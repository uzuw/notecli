# Changelog

All notable changes to `note`. Versions follow `MAJOR.MINOR.PATCH`; the version lives in the script
(`VERSION`) and is reported by `note --version`.

## Unreleased

### Added

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
