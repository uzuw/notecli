# Architecture

One process, one file, no daemon. `note` is a ~1500-line stdlib-only Python script (Python 3.11+)
that shells out to `nvim` (or `$EDITOR`), `fzf` and `ripgrep` when they exist.

```
        capture                         read/search                    manage
  ┌──────────────────┐            ┌──────────────────────┐      ┌──────────────────┐
  │ new (editor flow)│            │ ls / find / tag      │      │ rm / restore /gc │
  │ add  (args/stdin)│            │ show / open / last   │      │ reindex / where  │
  └────────┬─────────┘            └───────────┬──────────┘      └────────┬─────────┘
           │                                  │                          │
           ▼                                  ▼                          ▼
   write_note() ── atomic ──▶ notes/YYYY/MM/*.md        index.db (SQLite + FTS5) ── derived
                                   │                                  ▲
                                   └──────── sync() from mtime/size ───┘
```

## The one rule

**Markdown files are the only source of truth. `index.db` is a cache.**

Nothing is ever recorded that cannot be recomputed from the files: `sync()` walks `notes/**/*.md`,
compares `(mtime_ns, size)` against the index and reparses only what changed, then deletes rows whose
files disappeared. Consequences:

- editing, renaming or deleting notes in nvim, or with `mv`/`rm`, is picked up by the next command;
- deleting `index.db` is harmless (`note reindex`, or just any other command, rebuilds it);
- there is no locking, no watcher, no daemon, and no way for the index to be "ahead" of the files.

The cost is one directory walk plus `stat()` per note per command — sub-millisecond at thousands of
notes, far below the cost of starting the editor.

## Capture flows

**Editor flow (`note`, `note new`)**

1. Build front matter in memory: id, title, created/updated, tags, `cwd`, host, `git branch@sha`,
   tmux `session`, source.
2. Write the draft to `<root>/.tmp/<id>.md` (outside the indexed tree, so a half-written note can
   never appear in search) and open the editor at the end of the buffer (`nvim +`).
3. On exit, re-read the draft. Empty body → delete the draft, exit `0` ("empty note discarded").
   Otherwise merge any front-matter keys the user edited, derive the title from `title:` →
   first heading/first body line → filename, merge body `#hashtags` into tags, slug the filename and
   move the draft to `notes/YYYY/MM/YYYY-MM-DD_HHMMSS-slug.md`.

**Fast capture (`note add`)** skips the editor: first line = title, rest = body. **`note append`**
targets the newest note (or `--to REF`) and appends after a blank line.

Writers use `write_note()`: write `*.swp-tmp` next to the target, then `os.replace()` — atomic on
POSIX, so a crash mid-write cannot truncate an existing note.

## Search pipeline

1. `sync()` brings the index up to date.
2. `find` builds an FTS5 `MATCH` query: `\w+` tokens from the input, each quoted with a `*` prefix
   (`"comp"* "test"*`), implicitly ANDed. Quoting removes every FTS operator from user input, so
   punctuation or stray `"` cannot produce a syntax error.
3. Filters are SQL predicates on the `notes` table (`created_ts` bounds, tag membership via
   `' ' || tags || ' '` LIKE, `cwd` substring, exact `host`).
4. Ordering is `bm25(notes_fts, 8, 1, 3)` (title, body, tags) then `created_ts DESC, mtime_ns DESC,
   path DESC` — `mtime_ns` keeps notes created in the same second in true creation order, which
   whole-second ISO timestamps alone cannot express.
5. If FTS returns nothing, a `LIKE '%query%'` scan over the stored text runs instead; this covers
   punctuation-only queries and substrings that tokenization would split.
6. `-e/--regex` bypasses FTS entirely and runs `rg --json` over the notes tree instead, mapping
   matching lines into the snippet column of the picker.

`ls` (no query) skips steps 2–5 and just lists the newest rows with the same filters it supports.

## Pickers

`ls`, `find`, `tag`, `rm` and `restore` share one picker helper. Rows are `display<TAB>path`, and
fzf is told `--with-nth=1`, so the path column is invisible but available to the selection and to the
preview command (`note show --preview -- '{2}'`, which renders the metadata header plus body).

Degradation ladder: `fzf` present + tty → fzf. Otherwise a numbered prompt
(`1) …`, `1,3` for multi-select). Commands also short-circuit before the picker when stdout/stdin is
not a terminal (`--json`, `-p`, or a plain listing), so nothing hangs in scripts.

## Deletion model

`rm` moves files to `trash/<YYYY-MM-DD_HHMMSS>/<original relative path>` and writes a
`<name>.md.meta` sidecar with `{"original": "<absolute path>"}`; the index row is dropped in the same
command. `restore` walks the trash newest-bucket-first, moves the selection back to the recorded
path and reindexes it; a collision restores as `<stem>-restored.md`. `gc` prunes buckets by age

Trash lives under the same root, so a backup of the notes root also backs up what you deleted.

## Design decisions

| Decision | Why |
| --- | --- |
| Files are truth, index derived | Search is fast, but a stale or corrupted index can never lose a note. Removes sync bugs that plague two-way state. |
| SQLite FTS5 rather than `rg` for normal search | Ranking and metadata filters (`tag`, date, cwd, host) in one query; `rg` stays for regex. |
| Single file, no dependencies | Install is a symlink; nothing to break at 2 a.m. (`make install`, or drop the script on `PATH`). |
| `fzf`/`rg`/`nvim` optional | Each has a documented fallback; the tool is usable over SSH or on a box without them. |
| Trash instead of hard delete by default | Deleting a note is one keystroke and irreversible; a bucket plus `restore` makes it a two-step, undoable action. |
| Draft outside the indexed tree | An interrupted editor session can never leave a searchable half-note behind. |
| Front matter rewritten only on real change | `note open` does not touch your file if you changed nothing (`SHA1` comparison), so undo history and mtimes stay sane. |
| Metadata that can't be guessed is derived at read time | A file dropped in by hand (or stripped of front matter) still gets a title and timestamp from its filename/body instead of breaking the index. |

## Failure modes

| Situation | Behaviour |
| --- | --- |
| `index.db` deleted or corrupted | Rebuilt from files by the next command (`note reindex` forces it). |
| Note edited/deleted outside the tool | Picked up by `sync()`; no manual step. |
| Index schema changes between versions | `connect()` adds missing columns (`snippet`) and clears mtimes so affected rows are reparsed. |
| Editor exits non-zero | Reported on stderr; a non-empty draft is still saved, an empty one is discarded. |
| Draft deleted by the editor | `note` reports "draft vanished, nothing saved" and exits non-zero. |
| `note` killed mid-edit (or power loss) | The draft survives in `.tmp/`, invisible to search; `note where` counts it, `note recover` files it, `note gc` prunes it (1 h floor). |
| Two `note` processes at once | SQLite WAL + 10 s busy timeout: readers never queue behind writers; writers wait for each other instead of failing. |
| `fzf`/`rg`/`nvim` missing | Numbered picker / indexed substring search / `$VISUAL`/`$EDITOR`/`vi`. |
| Broken `config.toml` | Warning on stderr, defaults used; the tool never refuses to run because of config. |
| `rm` on a pipe without `-y` | Refuses with exit `1` instead of guessing. |
| Root directory is read-only / gone | OS error surfaces as a Python traceback (no special handling). |
