# simple_note — documentation

Documentation for the `note` CLI (code: this repository, GitHub: `uzuw/notecli`).

This directory holds **documentation only** — no code, no tests, no generated artifacts. Other
projects' docs live in sibling directories under `project_docs/`.

## Index

| Doc | Contents |
| --- | --- |
| [commands.md](commands.md) | Every command, alias and flag, with examples, exit codes and `--json` shapes |
| [architecture.md](architecture.md) | How it works: capture flows, index sync, search pipeline, pickers, design decisions |
| [storage.md](storage.md) | On-disk layout, front matter contract, index schema, recovery procedures |
| [configuration.md](configuration.md) | `config.toml` keys, environment variables, editor and picker precedence |
| [development.md](development.md) | Repository layout, test strategy, verification playbook, release checklist |
| [changelog.md](changelog.md) | Released and unreleased changes |

## Scope of these docs

- They describe the behaviour of the code in this repository, and are updated in the same commit
  as the change they describe. Where the working tree differs from the latest tag, the difference
  is listed under *Unreleased* in [changelog.md](changelog.md).
- The latest release is `v0.1.1`; `note --version` prints the version of the script you are running.
- Examples assume `note` is on `PATH` (`make install`).
