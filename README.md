# note

Frictionless note capture: `note` opens nvim on a fresh, pre-filled note. You type, `:wq`, and it is
already named, dated, timestamped, filed under `notes/YYYY/MM/`, tagged and searchable. No directory
hunting, no naming files, no renaming after the fact.

```
$ note                      # nvim opens on a new note, cursor at the end
$ note add "pin pytest-asyncio<0.24 to fix flaky CI" -t ci
$ note append --bullet "also bumped the runner timeout"
$ note find flaky           # full-text search -> fzf -> enter opens it
$ note ls                   # fuzzy browse everything
$ note rm                   # fuzzy multi-select -> trash (recoverable)
```

## Install

```sh
make install                # symlinks ./note into ~/.local/bin
make test                   # pytest suite
```

Requires Python 3.11+ (stdlib only, no dependencies). Recommended companions: `nvim`, `fzf`,
`ripgrep` (regex search). Everything degrades gracefully without them — notes are plain Markdown, and
the CLI falls back to a numbered picker when `fzf` is unavailable or stdin is not a terminal.

## Commands

| Command | What it does |
| --- | --- |
| `note` / `note new [title]` | Open the editor on a new note. Empty drafts are discarded. |
| `note add [text]` | Capture without the editor (args or stdin). |
| `note append [text]` | Append to the newest note (`--to REF` to target another, `--bullet` for `- HH:MM text`). |
| `note ls [query]` | Newest-first list in fzf; enter opens. |
| `note find <query>` | Indexed full-text search, ranked by relevance; enter opens. |
| `note find -e <regex>` | Regex search via ripgrep with matching lines as preview. |
| `note show <ref>` | Print a note raw (`--json` for metadata). |
| `note open <ref>` | Open by id, filename fragment, or fuzzy query (`--pick` to force the picker). |
| `note last` | Open the most recent note (`--show` to print it). |
| `note rm [query]` | Multi-select and move to trash (`--purge` for permanent, `-y` to skip the prompt). |
| `note restore` | Put trashed notes back where they were. |
| `note tags` / `note tag <name>` | Tag counts / notes carrying a tag. |
| `note reindex` | Rebuild the index from files. |
| `note gc [--days N]` | Purge trash entries older than N days (`--all` for everything). |
| `note where` | Paths, editor, index stats. |

`ls`, `find` and `rm` share the same filters: `-t/--tag`, `--since`, `--until` (`today`, `yesterday`,
`-7d`, `2026-10-01`), `--cwd`, `--host`; `ls`, `find` and `tag` take `-p/--print-path`.
`note add/new/append/ls/find/show/tags/where` take `--json` for scripting; `-q/--quiet` suppresses
chatter on the capture commands.

`note` with no arguments is the hot path, so bind it: `alias n=note`, a tmux key
(`bind n display-popup -E note`), or a desktop keybind running `foot -e note`.

## Where notes live

```
~/.local/share/note/
├── index.db                                   # derived SQLite FTS5 index (safe to delete)
├── notes/2026/10/2026-10-06_143205-fix-flaky-ci.md
└── trash/2026-10-06_151233/2026/10/2026-10-06_143205-fix-flaky-ci.md
```

The Markdown files are the only source of truth. The index is rebuilt from file mtime/size on every
command, so editing, renaming or deleting notes by hand (or with nvim plugins) is reflected
automatically — `note reindex` only matters if the `.db` is lost or corrupted.

Each note carries the context it was captured in:

```markdown
---
id: 20261006-143205-a1b2
title: Fix flaky CI
created: 2026-10-06T14:32:05+05:45
updated: 2026-10-06T14:41:11+05:45
tags: [ci, python]
cwd: /home/you/code/api
host: laptop
git: main@4f2c1ab
session: work:2.1
source: editor
---

Free-form Markdown body. Inline #hashtags become tags.
```

`note` only rewrites front matter when the body changed (to bump `updated`) or when appending, so
hand edits to unknown YAML keys survive. Hashtags found in the body are merged into `tags`.

## Configuration

`~/.config/note/config.toml`, all keys optional:

```toml
root = "~/notes"            # where notes/ , trash/ and index.db live
editor = "nvim -f"          # editor command (see precedence below)
template = "# {title}\n\n"  # body pre-filled in new notes
fzf_opts = "--height=90% --layout=reverse --border --info=inline"
limit = 50                  # default number of rows in pickers
```

Precedence for the editor: `--editor` > `$NOTE_EDITOR` > `config.editor` > `nvim` if installed >
`$VISUAL`/`$EDITOR` > `vi`. `nvim`/`vim` are launched at the end of the file (`+`). Other environment
variables: `NOTE_HOME` (root), `NOTE_NO_FZF=1` (force the built-in picker), `NO_COLOR` (no ANSI).

`--root` overrides everything, which is handy for scratch notebooks: `note --root /tmp/scratch ls`.

## Notes on behaviour

- The editor flow writes a draft in `<root>/.tmp/`, then slugs the final filename from the edited
  `title:` (or the first body line). If the buffer is left empty the draft is deleted — no empty
  notes, ever.
- `rm` moves notes to `trash/<timestamp>/` preserving their path and a `.meta` pointer, so
  `note restore` is lossless.
- Interrupted or concurrent runs are safe: writes are atomic (`os.replace`) and deletes only touch
  paths the index knows about.

## Development

```sh
make test        # pytest tests/ (43 tests, no network, isolated NOTE_HOME)
make check       # byte-compile the CLI
```

The whole tool is the single executable file `note` (stdlib only, no dependencies). Tests drive the
real binary as a subprocess with a stubbed editor; one test runs the real `fzf` picker on a pty.
