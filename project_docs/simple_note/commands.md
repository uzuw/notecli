# Command reference

```
note [-h] [-V] [--root ROOT] [--editor EDITOR] [--json] [-q] <command> [args]
```

Run `note` with no command to start a new note. If the first word is not a known command it is
treated as the **title of a new note**, so `note buy milk` creates a note titled "buy milk" without
typing `new`. Global flags may lead (`note --root /tmp/scratch ls`); only the first word is
inspected, so flag values are never mistaken for titles.

Two consequences worth knowing: a typo'd subcommand creates a (recoverable) note instead of an
error — visible in `note ls`, removable with `note rm` — and a title that collides with a command
name needs the explicit form: `note new rm the old notes`.

## Aliases

| Command | Aliases |
| --- | --- |
| `note new` | `n`, *(default)* |
| `note add` | `a`, `q` |
| `note append` | `ap` |
| `note ls` | `list`, `l` |
| `note find` | `f`, `search`, `s` |
| `note show` | `cat` |
| `note open` | `edit`, `e` |
| `note rm` | `delete`, `d` |
| `note restore` | `undo` |
| `note tags` | `t` |
| `note where` | `info` |

## Global flags

Accepted both before and after the command word (`note --json ls` ≡ `note ls --json`).

| Flag | Effect |
| --- | --- |
| `--root PATH` | Use a different notes root for this run (overrides `$NOTE_HOME` and config) |
| `--editor CMD` | Override the editor command for this run |
| `--json` | Machine-readable output where supported (see [JSON shapes](#json-shapes)) |
| `-q`, `--quiet` | Suppress chatter; `add`/`new` print only the path |
| `-V`, `--version` | Print `note <version>` |
| `-h`, `--help` | Help for the CLI or a single command (`note find -h`) |

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success (including "picker cancelled" and "empty note discarded") |
| `1` | User-level failure: no matches, unknown reference, nothing to add, deletion aborted, missing `--yes` for a piped delete |
| `2` | Usage error (unknown flag, missing argument) — emitted by argparse |
| `130` | Interrupted (Ctrl-C) |

## Reference resolution

`show`, `open`, `append --to`, `last` and `edit` accept a reference. It is resolved in this order:

1. an existing file path (`~/notes/...`, absolute or relative);
2. a path relative to the notes root (`2026/10/2026-10-06_143205-fix-flaky-ci.md`);
3. an exact note id (`20261006-143205-a1b2`) or exact filename stem;
4. the newest note whose filename stem contains the fragment (`.md` suffix optional);
5. the newest note whose title contains the fragment;
6. otherwise a full-text search: a single hit opens directly, several hits open an fzf picker,
   no hits exit `1` with `no note matching '<ref>'`.

---

## Capture

### `note new [title...]` (`n`)

Opens `$EDITOR` on a fresh draft. The draft is pre-filled with front matter (including the title if
given on the command line) and, when configured, the body `template`.

| Flag | Effect |
| --- | --- |
| `-t`, `--tag TAG` | Pre-fill tags (repeatable, comma-separated) |
| `--no-editor` | Skip the editor: build the note from the title plus stdin |

Behaviour: the draft lives in `<root>/.tmp/<id>.md`; the final path is chosen after the editor
exits. If the body is empty the draft is deleted and nothing is written. Otherwise the filename is
slugged from the edited `title:` (or the first body line) and the note is filed under
`notes/YYYY/MM/`. Existing notes are never renamed by this command.

```sh
note                                  # blank note, cursor at the end of the buffer
note "deploy checklist"               # new note pre-titled
note new "ledger design" -t arch      # pre-titled and pre-tagged
echo "body from a pipe" | note new "piped" --no-editor
```

### `note add [text...]` (`a`, `q`)

Captures without an editor. The first line becomes the title, the rest the body; with shell
arguments the whole string is the title. Text can come from stdin (`cmd | note add`).

```sh
note add "pin pytest-asyncio<0.24 to fix flaky CI" -t ci
printf 'Ledger design\nUse an append-only log.\n#arch\n' | note add
```

Inline `#hashtags` in the text become tags, merged with `-t` values.

### `note append [text...]` (`ap`)

Appends to the newest note, separated by a blank line, and bumps `updated`.

| Flag | Effect |
| --- | --- |
| `--to REF` | Target another note instead of the newest |
| `--bullet` | Prefix a single-line entry with `- HH:MM` |
| `-t`, `--tag TAG` | Add tags if missing |

```sh
note append --bullet "also bumped the runner timeout"
echo "raw paste" | note append --to 20261006-143205-a1b2
```

---

## Browse and search

### `note ls [query]` (`list`, `l`)

Newest-first list in the fzf picker (enter opens, tab multi-selects, `esc` cancels). A positional
query seeds the picker's search box. Without a terminal it prints the rows.

| Flag | Effect |
| --- | --- |
| `-n`, `--number N` | Max rows (default: `limit` from config, 50) |
| `-t`, `--tag TAG` | Only notes carrying the tag (repeatable) |
| `--since WHEN` | Only notes created at/after `WHEN` |
| `-p`, `--print-path` | Print instead of opening |

### `note find [query...]` (`f`, `search`, `s`)

Full-text search over title, body and tags (SQLite FTS5, `bm25` weighted 8 / 1 / 3). Single tokens
match by prefix (`comp` finds "compaction"); all terms must match. If the FTS query returns nothing,
a substring scan over the stored text runs as a fallback, which also covers punctuation-only
queries. Ranking: relevance, then newest first.

| Flag | Effect |
| --- | --- |
| `-t`, `--tag TAG` | Filter by tag (repeatable, ANDed) |
| `--since WHEN` / `--until WHEN` | Creation bounds (`--until` with a bare date includes that day) |
| `--cwd SUBSTRING` | Notes captured under a directory |
| `--host NAME` | Notes captured on a host |
| `-e`, `--regex` | Regex search via `ripgrep` instead of FTS (matching lines become the snippet) |
| `-n`, `--number N` | Max results |
| `--sort rank\|date` | Relevance (default) or newest first |
| `-p`, `--print-path` | Print instead of opening |

At least one query term or filter is required.

### Date grammar (`--since`, `--until`)

| Form | Meaning |
| --- | --- |
| `today`, `yesterday` | Midnight local time of that day |
| `-7d`, `7d`, `-2w`, `-3m`, `-1y` | N days/weeks/months(30d)/years(365d) back, at midnight |
| `2026-10-06` | That day, 00:00 |
| `2026-10-06T14:32:05`, `2026-10-06 14:32` | Exact local time |
| `2026-10`, `2026` | First instant of the month/year |

Anything else exits `1` with `unrecognized date: '<input>'`. `--until` with a day-granularity value
is inclusive of that whole day (it compares against the end of the day).

```sh
note find flaky
note find -t arch --since -7d
note find --cwd /home/you/code/api --host laptop
note find -e 'timeout=(30|60)\b'
```

### `note tag <name>` and `note tags` (`t`)

`note tags` prints tag counts, most used first (`--json` gives `{"tag": count}`).
`note tag arch` lists notes carrying that tag in the picker (`-n`, `-p` supported).

### `note last`

Opens the newest note (`--show` prints it, `-n N` takes the newest N).

---

## Read

### `note show <ref>`

Prints a note. Default output is the raw file including front matter; `--preview` prints a coloured
header (title, date, tags, cwd, git, tmux session) plus the body — this is what the fzf preview
pane runs. `--json` prints the note object(s).

### `note open <ref>` (`edit`, `e`)

Opens a note in the editor. `--pick` always shows the picker instead of resolving directly;
`-n N` bounds the picker.

---

## Manage

### `note rm [query]` (`delete`, `d`)

Moves notes to the trash: `trash/<YYYY-MM-DD_HHMMSS>/<original path>` plus a `<name>.md.meta`
pointer holding `{"original": "<path>"}`. The index row is removed in the same operation.

| Flag | Effect |
| --- | --- |
| `-t`, `--tag TAG` | Candidate filter |
| `-n`, `--number N` | Max candidates |
| `-a`, `--all` | Select every match (no picker) |
| `-y`, `--yes` | Skip the confirmation prompt |
| `--purge` | Delete permanently instead of trashing |

Confirmation: with a terminal, candidates are multi-selected in fzf and then confirmed with a
`delete? [y/N]` prompt. With piped stdin and no `-a`/`-y`, the command refuses to guess and exits
`1`. `--purge` is irreversible.

```sh
note rm                         # pick and trash
note rm -t scratch -a -y        # everything tagged scratch, no prompt (still recoverable)
echo y | note rm old -a         # scripted
```

### `note restore` (`undo`)

Lists trash entries (newest bucket first) in the picker and moves the selection back to its
recorded original path. With exactly one entry, or without a terminal, it restores directly unless
`-a` selects everything. If the original path is occupied, the note is restored next to it as
`<stem>-restored.md`.

### `note gc [--days N | --all]`

Purges trash buckets: `-d/--days N` (default 30) keeps buckets newer than N days, `-a/--all` drops
everything. Stray files left directly in the trash root are removed too. Bucket age comes from the
timestamp in the bucket directory name, falling back to its mtime.

### `note reindex`

Drops and rebuilds the whole index from the note files. Rarely needed: every command already
resyncs changed, new and deleted files from mtime/size.

### `note where` (`info`)

Prints root, notes, trash and index paths, the resolved config file, editor, availability of `fzf`
and `rg`, note count, newest note, index size, and the `NOTE_*` environment variables.

---

## JSON shapes

Note objects (returned by `add`/`new`, `ls`, `find`, `tag`, `show`) contain:

```json
{
  "path": "/home/you/.local/share/note/notes/2026/10/2026-10-06_143205-fix-flaky-ci.md",
  "rel": "notes/2026/10/2026-10-06_143205-fix-flaky-ci.md",
  "id": "20261006-143205-a1b2",
  "title": "Fix flaky CI",
  "created": "2026-10-06T14:32:05+05:45",
  "updated": "2026-10-06T14:41:11+05:45",
  "tags": ["ci", "python"],
  "cwd": "/home/you/code/api",
  "host": "laptop",
  "git": "main@4f2c1ab",
  "session": "work:2.1",
  "source": "editor",
  "body": "full note body\n",
  "snippet": "first non-empty body line"
}
```

`tags` (per tag), `where` (see above) and `reindex`/`rm`/`restore`/`gc` (text only) differ; `find`
and `ls` return arrays, `show --json` returns an array with one object per note.

Empty result sets print `[]` and exit `1`, so scripts can distinguish "no hits" from "bad usage"
(exit `2`) without parsing stderr.

### Scripting examples

```sh
note find --since today --json | jq -r '.[].rel'
note ls -n 5 -p | xargs -o nvim
note tags --json | jq -r 'to_entries[] | "\(.value)\t\(.key)"'
cd "$(note show --json "$(note last --json | jq -r '.[0].title')" | jq -r '.[0].cwd')"
```
