# Configuration

`note` runs with zero configuration. Everything below is optional.

## Paths

| Thing | Default | Override |
| --- | --- | --- |
| Root (notes, trash, index) | `$XDG_DATA_HOME/note`, else `~/.local/share/note` | `$NOTE_HOME`, then config `root`, then `--root PATH` (highest priority) |
| Config file | `$XDG_CONFIG_HOME/note/config.toml`, else `~/.config/note/config.toml` | — |
| Notes / trash / drafts / index | `<root>/notes`, `<root>/trash`, `<root>/.tmp`, `<root>/index.db` | — |

`--root` and `$NOTE_HOME` expand `~`. Use them for scratch notebooks:
`note --root /tmp/scratch ls`.

## config.toml

```toml
root = "~/notes"            # where notes/, trash/ and index.db live
editor = "nvim -f"          # editor command line (shell-quoted, so arguments are fine)
template = "# {title}\n\n"  # body pre-filled in new notes
fzf_opts = "--height=90% --layout=reverse --border --info=inline"
limit = 50                  # default row count for pickers and searches
```

| Key | Type | Notes |
| --- | --- | --- |
| `root` | string | Beaten by `$NOTE_HOME` and `--root` |
| `editor` | string | Split with `shlex.split`, so `nvim -f -u NONE` works |
| `template` | string | Placeholders: `{title}`, `{date}` (`YYYY-MM-DD`), `{time}` (`HH:MM`), `{datetime}` (ISO) |
| `fzf_opts` | string | Appended to the built-in defaults; useful for `--preview-window`, `--select-1`, `--no-sort`, `--border=none` |
| `limit` | int | Default `50`; per-command `-n/--number` overrides it |

A malformed or unreadable `config.toml` prints a warning to stderr and is ignored — config problems
never prevent the tool from running.

## Editor resolution

First match wins:

1. `--editor CMD`
2. `$NOTE_EDITOR`
3. `editor` in `config.toml`
4. `nvim`, if it is on `PATH`
5. `$VISUAL`, then `$EDITOR`
6. `vi`

`nvim`, `vim`, `vi`, `neovim` and `nvim-qt` are launched as `EDITOR + FILE`, which puts the cursor on
the last line of the buffer (i.e. the end of the body, since front matter sits on top). Any other
editor is launched as `EDITOR FILE`. Multi-select opens one editor session with all selected notes
as buffers.

## Environment variables

| Variable | Effect |
| --- | --- |
| `NOTE_HOME` | Root directory (overrides `XDG_DATA_HOME`; beaten by `--root`) |
| `NOTE_EDITOR` | Editor command (overrides config; beaten by `--editor`) |
| `NOTE_NO_FZF` | Any non-empty value disables fzf and forces the numbered picker |
| `NO_COLOR` | Disables ANSI colour in listings and previews |
| `XDG_DATA_HOME` | Base for the default root |
| `XDG_CONFIG_HOME` | Base for the config file location |

## Picker behaviour

- fzf is used only when it is installed, stdin is a terminal, and `NOTE_NO_FZF` is unset.
- Rows are `display<TAB>path` with `--with-nth=1`, so the path column drives the selection and the
  preview command; the preview runs `note show --preview -- <path>`.
- Colour is enabled only when stdout is a terminal and `NO_COLOR` is unset.
- When stdout is not a terminal (or `--json`/`-p` is given), list commands print rows instead of
  launching a picker, which is what makes them safe inside pipelines.

## Tuning examples

```toml
# Prefer a compact picker anchored to the bottom, and skip the sound/border noise
fzf_opts = "--height=40% --layout=reverse-list --border=none"

# Keep a standing template for meeting notes
template = "## Context\n\n## Decisions\n\n## Follow-ups\n"

# Work out of a synced directory
root = "~/Sync/notes"
```

```sh
# One-off experiments without touching the config file
NOTE_HOME=/tmp/scratch note add "throwaway idea"
note --root /tmp/scratch find idea -p
NOTE_EDITOR='nvim -u NONE' note "minimal editor"
NOTE_NO_FZF=1 note ls            # numbered picker, e.g. over a slow SSH link
```
