# Storage format

## Directory layout

```
~/.local/share/note/                      # root: $NOTE_HOME > config.root > $XDG_DATA_HOME/note
├── index.db                              # SQLite + FTS5, derived — safe to delete
├── .tmp/<id>.md                          # in-flight editor drafts (never indexed)
├── notes/2026/10/2026-10-06_143205-fix-flaky-ci.md
└── trash/2026-10-06_151233/2026/10/2026-10-06_143205-fix-flaky-ci.md
    └── …/2026-10-06_143205-fix-flaky-ci.md.meta
```

- Notes are namespaced by creation **year/month directories** and by a **full timestamp in the
  filename** (`YYYY-MM-DD_HHMMSS-slug.md`), so the tree is self-describing and sorts chronologically
  even without the index. Collisions within the same second get a `-2`, `-3` suffix.
- Drafts live in `.tmp/` so an interrupted editor session is not searchable. A draft is
  deleted as soon as the note is filed or found to be empty; if the process dies first it stays
  until `note recover` files it or `note gc` prunes it (drafts younger than an hour are always
  kept, even by `gc --all`).
- Trash preserves the original relative path inside a timestamped bucket
  (`trash/<YYYY-MM-DD_HHMMSS>/notes/2026/10/...`), so a restore is a plain move back.

## Front matter

```markdown
---
id: 20261006-143205-a1b2
title: Fix flaky CI test
created: 2026-10-06T14:32:05+05:45
updated: 2026-10-06T14:41:11+05:45
tags: [ci, python]
cwd: /home/you/code/api
host: laptop
git: main@4f2c1ab
session: work:2.1
source: editor
---

Body in Markdown. Inline #hashtags are merged into tags.
```

| Field | Source | Notes |
| --- | --- | --- |
| `id` | generated | `YYYYMMDD-HHMMSS-<4 hex>`; stable identifier used by references |
| `title` | CLI / editor / derived | Written even when empty (`title: ""`) so it can be filled in the editor |
| `created` | capture time | Local time with UTC offset; drives the filename and the date directories |
| `updated` | rewritten on change | Only bumped when the file content actually changed (SHA1 comparison) |
| `tags` | `-t`, `#hashtags`, editor | Inline list; deduplicated, order preserved |
| `cwd` | capture directory | `--cwd` filters on this |
| `host` | `uname().nodename` | `--host` filters on this |
| `git` | `branch@short-sha` | Omitted outside a repository |
| `session` | `tmux #S:#I.#P` | Omitted outside tmux |
| `source` | `editor` or `cli` | Which capture path created the note |

Parser tolerance: plain `key: value`, quoted values, inline lists (`[a, b]`) and block lists
(`- item`) are all accepted; unknown keys are preserved on rewrite; a file with no front matter at
all is accepted and gets its title/timestamp from the first body line and the filename.
Writer discipline: values are quoted only when needed, empty scalars are dropped (except `title`
and `tags`), and rewrites go through a temp file + `os.replace()`.

## Derived fields

Nothing below is stored in the file:

- **title fallback**: front matter `title:` → first `#` heading → first body line → filename.
- **slug**: NFKD-folded, lowercased, non-word characters collapsed to `-`, first 6 words, ≤48 chars,
  `note` as the last resort.
- **tags**: front matter tags plus every inline `#hashtag` matched by
  `(?<![\w#])#([A-Za-z][\w/\-]*)` (so a `# ` heading is not a tag).
- **snippet**: first non-empty body line, markdown markers stripped, ≤72 chars.

## Index schema

```sql
CREATE TABLE notes (
  id INTEGER PRIMARY KEY, path TEXT UNIQUE, uid TEXT, title TEXT,
  created TEXT, created_ts REAL, updated TEXT, updated_ts REAL,
  mtime_ns INTEGER, size INTEGER,          -- sync keys
  tags TEXT, snippet TEXT, cwd TEXT, host TEXT, git TEXT, session TEXT, source TEXT
);
CREATE VIRTUAL TABLE notes_fts USING fts5(title, body, tags, tokenize="unicode61 remove_diacritics 2");
```

- `notes_fts.rowid` mirrors `notes.id`; the FTS table stores its own copy of the text (no external
  content table), which keeps deletes trivial.
- `mtime_ns`/`size` are the change-detection keys: a row is reparsed only when either differs.
- Rank weighting `bm25(notes_fts, 8.0, 1.0, 3.0)` = title, body, tags.
- Schema upgrades are handled in `connect()`: missing columns are added (`snippet`) and
  `mtime_ns` is cleared so existing rows are reparsed once.

## Recovery procedures

| Symptom | Fix |
| --- | --- |
| Search misses a note you can see on disk | Any command resyncs; `note reindex` forces a full rebuild |
| `index.db` deleted, corrupted or from an older schema | `note reindex` (or just run any command) |
| Note restored from a backup without front matter | It is indexed anyway; title/timestamp come from the body and filename |
| Deleted a note by mistake | `note restore` (picker), `note restore -a` (everything) |
| Trash growing | `note gc -d 7`, or `--all` to empty it |
| `note where` reports abandoned drafts | `note recover` files them (timestamp comes from the draft), `note gc` prunes them |
| `index.db-wal` / `index.db-shm` next to the index | Normal for SQLite WAL mode; they checkpoint away, and both are as disposable as `index.db` |
| Want a second, throwaway notebook | `note --root /tmp/scratch …` or `NOTE_HOME=/tmp/scratch note …` |
| Backups | Copy the root; `notes/` is the value, `index.db` is disposable |
