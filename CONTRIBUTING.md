# Contributing to reqstool-python-poetry-plugin

Thank you for your interest in contributing!

For DCO sign-off, commit conventions, and code review process, see the organization-wide [CONTRIBUTING.md](https://github.com/reqstool/.github/blob/main/CONTRIBUTING.md).

## Prerequisites

- Python 3.13+
- [Poetry](https://python-poetry.org/)

## Setup

```bash
git clone https://github.com/reqstool/reqstool-python-poetry-plugin.git
cd reqstool-python-poetry-plugin
poetry install
```

If using Claude Code, regenerate the `opsx` slash commands and OpenSpec skills
(`.claude/commands/opsx/`, `.claude/skills/openspec-*`) after cloning — they're
CLI-generated tool scaffolding, not committed to the repo:

```bash
openspec update   # or: openspec init --tools claude --force
```

## Build & Test

```bash
poetry build
poetry run pytest
```
