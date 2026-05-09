# Mise Environment Skill

## Purpose

Set up a repeatable local Python toolchain with mise for this repository.

## Steps

1. Install toolchain versions from `mise.toml`.
2. Sync dependencies with `uv sync --all-extras`.
3. Verify CLI is available with `uv run promptbench --help`.

## Validation

- `mise doctor` reports no errors.
- `uv run pytest -q` starts test discovery.
