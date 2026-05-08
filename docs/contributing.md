# Contributing

## Development Setup

This repo uses [`mise`](https://mise.jdx.dev/) for toolchain management (Python 3.14, uv, Rust) and [`uv`](https://github.com/astral-sh/uv) for dependency management.

```bash
git clone <repo-url>
cd promptbench

# Install toolchain (Python 3.14, uv, Rust)
mise install

# Install dependencies
mise x -- uv sync

# Verify install
mise x -- uv run -- promptbench --help
```

## Running Tests

```bash
mise x -- uv run -- pytest
```

Tests are under `tests/` with `src/` on the Python path (configured in `pyproject.toml`).

## Test Coverage

| Test file | What it covers |
|---|---|
| `test_config_loader.py` | YAML parsing, schema validation, default values |
| `test_dynamic_concurrency.py` | Concurrency resolution hierarchy, model chain fallback |
| `test_e2e_local_config.py` | Full workflow integration (review, eval, eval-all) |
| `test_eval_loader.py` | Eval definition discovery and deduplication |
| `test_limits.py` | Size limit resolution order and boundary checks |
| `test_model_ids.py` | `provider/model-name` format parsing |
| `test_report_command.py` | Markdown report generation and telemetry aggregation |
| `test_repository.py` | ORM: run creation, artifact upsert, measurement persistence |
| `test_runtime_logging.py` | Log level filtering, payload truncation |
| `test_strict_model_success.py` | `require_model_success` policy enforcement |
| `test_web_app.py` | Flask routes, failure diagnostics UI, healthcheck endpoint |
| `test_workflows_eval.py` | Size cap gating, multi-test scoring, fallback model chains |

## Project Structure

```
src/promptbench/
├── cli/            Typer app + command modules
├── config/         YAML loader + Pydantic schema
├── artifacts/      File resolution + ArtifactDocument dataclass
├── evals/          Eval definition loading + prompt selection
├── provider/       Model ID parsing + provider/concurrency resolution
├── workflows/      Review, eval, enhance logic + LLM output models
├── validators/     Artifact-type validation (skills frontmatter check)
├── reporting/      SQLModel ORM, DB init, query layer
└── web/            Flask dashboard app
```

## Code Conventions

- Typed Python throughout (Pydantic models, dataclasses, type annotations)
- `snake_case` for functions and variables, `PascalCase` for classes
- Each module has a single clear responsibility
- Secrets via environment variables only — never hardcoded

## Local E2E Testing

Use the included LMStudio config and sample artifacts for end-to-end testing without a cloud API:

```bash
export LLMSTUDIO_API_KEY=dummy

mise x -- uv run -- promptbench eval skills sample-skill.md \
  --enhance --loop 3 \
  --config promptbench.local.yaml \
  --repo .
```

See [configuration.md](configuration.md) for full local config details.

## Submitting Changes

1. Fork the repo
2. Create a feature branch
3. Run `pytest` — all tests must pass
4. Open a PR against `main`
