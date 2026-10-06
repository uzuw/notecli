# Development

## Repository layout

```
note                        # the entire CLI: one executable Python file, no dependencies
tests/test_note.py          # 47 pytest cases driving the real binary
Makefile                    # install / uninstall / test / check
README.md                   # user-facing quick start (root of the repo)
project_docs/simple_note/   # these documents
```

There is no package structure, no build step and no third-party runtime dependency. `pip`, `venv`
and `setuptools` are not involved: `make install` symlinks `note` into `$PREFIX/bin`
(default `~/.local/bin`).

## Working on it

```sh
make check     # python3 -m py_compile note
make test      # python3 -m pytest tests/ -q
make install   # symlink into ~/.local/bin (notes data untouched)
```

Manual smoke test against a throwaway root, with no editor and no picker:

```sh
export NOTE_HOME=/tmp/scratch XDG_CONFIG_HOME=/tmp/scratch-cfg
note add "smoke test #demo"
note find demo -p
note ls -p
note rm demo -a -y && note restore -a
note where
```

## Test strategy

Tests execute the real script as a subprocess with an isolated `NOTE_HOME`/`XDG_CONFIG_HOME` and a
stubbed editor (`$NOTE_EDITOR` points at a small shell script that appends `$FAKE_BODY` and can
retitle or blank the draft), so the editor flow — including discard-on-empty and slug-from-title —
is covered without a terminal. Selection logic is covered three ways:

1. non-tty paths (`--json`, `-p`) for listing and filtering;
2. the numbered picker via `NOTE_NO_FZF=1`;
3. the real `fzf` picker on a pty, driven with `--select-1` so a single match is chosen without
   keystrokes, asserting the exact file handed to the editor.

Coverage map:

| Area | Representative cases |
| --- | --- |
| Slugging, front matter | unicode/long/empty titles, quoted values, block lists, files without front matter |
| Capture | `add` from args and stdin, title/body split, hashtag tags, context fields, empty stdin |
| Editor flow | rename by edited title, draft cleanup, blanked draft discarded, missing draft |
| Index sync | external edit picked up, external delete pruned, `index.db` deleted and rebuilt |
| Search | title/body hits, prefix matching, punctuation fallback, tag/date filters, `--sort`, ripgrep regex |
| References | by id, filename stem, `.md` basename, notes-relative path, title fragment, unknown ref |
| Deletion | confirm/abort, trash layout + `.meta`, `--purge`, piped-without-`-y` refusal, restore, gc |
| Output contracts | `--json` shapes, full `body` vs `snippet`, exit codes |
| Editor invocation | `nvim` gets `+`; other editors do not |

Known gaps in coverage (see also the release notes): the fzf multi-select plus delete-confirmation
pair has only been exercised in parts, and the ripgrep-absent fallback for `find -e` has not been
triggered in CI (ripgrep is installed on the development machine).

## Verification playbook

These are the checks used before a release, in order of how much they prove:

```sh
make check && make test                                   # unit + integration suite

# real editor, no terminal needed: Ex mode appends two body lines and writes
printf "call append(line('$'), 'body from real nvim')\nwq\n" \
  | NOTE_HOME=/tmp/vr NOTE_EDITOR="nvim -es" note
NOTE_HOME=/tmp/vr note find nvim --json | jq '.[0] | {title, tags, source}'

# real fzf picker path (pty + --select-1 so no keystrokes are required)
# see tests/test_note.py::test_fzf_picker_opens_the_selected_note

# real ripgrep regex path: 'a|b' matches via rg but not via tokenized FTS
note find -e 'Pytest|Kafka' --json

# default root and installed binary
note where | head -6
```

Claims worth re-checking whenever the corresponding code changes: exit codes, the `--json` field
set, `body` being the full body while `snippet` is the first line, ordering
(`created_ts DESC, mtime_ns DESC, path DESC`), and the trash layout.

## Code conventions

- One file, section banners (`# ---- name`), dataclasses for records (`Note`, `Cfg`), pure helpers
  for anything formatting- or parsing-related so they can be unit-tested by importing the script.
- No new runtime dependencies; if a feature needs one, it needs a documented fallback first.
- Every path that writes user data goes through `write_note()` (temp file + `os.replace`) and every
  command that reads index data calls `sync()` first.
- Errors users can act on go through `die()` (message on stderr, exit `1`); unexpected exceptions
  are allowed to traceback rather than being swallowed.

## Release checklist

```sh
# 1. version bump in the script (single source of truth: VERSION = "x.y.z")
# 2. changelog entry + doc updates in the same commit
make check && make test
git commit -am "release: vX.Y.Z"
git tag -a vX.Y.Z -m "note X.Y.Z"
git push origin main vX.Y.Z
gh release create vX.Y.Z ./note --title "note X.Y.Z" --notes-file <notes> --verify-tag
```

The release asset is the script itself, so it can be downloaded and `chmod +x`-ed; verify with
`cmp` against the repository file and by running `./note --version` on the downloaded copy.
