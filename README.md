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
make test                   # 53 tests
```

Requires Python 3.11+ (stdlib only, no dependencies). Recommended companions: `nvim`, `fzf`,
`ripgrep` — all optional. Without them `note` falls back to `$EDITOR`, a numbered picker and indexed
substring search. The same script is attached to the [latest
release](https://github.com/uzuw/notecli/releases); download it, `chmod +x`, put it on `PATH`.

## Commands

| Command | What it does |
| --- | --- |
| `note` / `note new [title]` | Open the editor on a new note. Empty drafts are discarded. |
| `note add [text]` | Capture without the editor (arguments or stdin). |
| `note append [text]` | Append to the newest note (`--to REF`, `--bullet` for `- HH:MM text`). |
| `note ls [query]` | Newest-first list in the fzf picker; enter opens. |
| `note find <query>` | Ranked full-text search; enter opens. `-e` for ripgrep regex. |
| `note show <ref>` | Print a note (`--preview` for the coloured view, `--json` for metadata). |
| `note open <ref>` | Open by id, filename fragment, path or query. |
| `note last` | Open the newest note (`--show` to print it). |
| `note rm [query]` | Multi-select and move to trash (`--purge`, `-y`, `-a`). |
| `note restore` | Put trashed notes back where they were. |
| `note recover` | File drafts left behind by a killed run (`where` counts them). |
| `note tags` / `note tag <name>` | Tag counts / notes carrying a tag. |
| `note reindex`, `note gc`, `note where` | Rebuild the index, purge trash, show paths and stats. |
| `note help [command]` | List the commands, or describe one (`note help rm`). |

Filters: `ls` takes `-t/--tag` and `--since`; `find` takes `-t/--tag`, `--since`, `--until`, `--cwd`,
`--host`; `rm` takes `-t/--tag`. `ls`, `find` and `tag` take `-p/--print-path`.
`add/new/append/ls/find/show/tags/where` take `--json` for scripting.

`note` with no arguments is the hot path, so bind it: `alias n=note`, a tmux key
(`bind n display-popup -E note`), or a desktop keybind running `foot -e note`.

## Where notes live

```
~/.local/share/note/
├── index.db                                   # derived SQLite FTS5 index (safe to delete)
├── notes/2026/10/2026-10-06_143205-fix-flaky-ci.md
└── trash/2026-10-06_151233/2026/10/2026-10-06_143205-fix-flaky-ci.md
```

Markdown files are the only source of truth; the index is resynced from file mtime/size on every
command, so editing, renaming or deleting notes by hand is reflected automatically. Each note
records the context it was captured in — `cwd`, host, git `branch@sha`, tmux session — in its front
matter, and inline `#hashtags` become tags.

Config lives in `~/.config/note/config.toml` (`root`, `editor`, `template`, `fzf_opts`, `limit`);
environment: `NOTE_HOME`, `NOTE_EDITOR`, `NOTE_NO_FZF`, `NO_COLOR`.

## Documentation

Full documentation is in [`project_docs/simple_note/`](project_docs/simple_note/):

| Doc | Contents |
| --- | --- |
| [commands.md](project_docs/simple_note/commands.md) | Every command, flag, exit code and JSON shape |
| [architecture.md](project_docs/simple_note/architecture.md) | Capture flows, index sync, search pipeline, design decisions |
| [storage.md](project_docs/simple_note/storage.md) | On-disk layout, front matter contract, index schema, recovery |
| [configuration.md](project_docs/simple_note/configuration.md) | `config.toml`, environment, editor and picker precedence |
| [development.md](project_docs/simple_note/development.md) | Test strategy, verification playbook, release checklist |
| [changelog.md](project_docs/simple_note/changelog.md) | Released and unreleased changes |

## Development

```sh
make test        # pytest tests/ — isolated NOTE_HOME, stubbed editor, real fzf on a pty
make check       # byte-compile the CLI
```

The entire tool is the single executable file `note`. See
[development.md](project_docs/simple_note/development.md) for the test strategy and the release
checklist.

## License

[MIT](LICENSE) — the copyright holder is listed as `uzuw`; change that line if you want your legal
name there instead.

## Known limitations

- Linux/POSIX only; not exercised on macOS or Windows.
- The fzf multi-select plus delete-confirmation pair has been verified in parts, not in one
  interactive session.
- Local, single-user: no sync, multi-device or encryption.
