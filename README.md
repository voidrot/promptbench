# PromptBench

PromptBench is a CLI for evaluating and improving agent artifacts (skills, prompts, agents, tools).

## Stack

- Python + Typer CLI
- Pydantic/PydanticAI for config + model workflow contracts
- SQLite + SQLModel for persistent logs/metrics
- Flask + Jinja2 for local dashboard (`serve`)

## Setup (mise)

This repo uses `mise` for toolchain management.

```bash
mise install
mise x -- uv sync
```

## CLI

```bash
mise x -- uv run -- promptbench init
mise x -- uv run -- promptbench review skills path/to/skill.md
mise x -- uv run -- promptbench eval skills path/to/skill.md --enhance --loop 3
mise x -- uv run -- promptbench eval-all skills --loop 2
mise x -- uv run -- promptbench report
mise x -- uv run -- promptbench serve --host 127.0.0.1 --port 8080
```

## Local LLMStudio E2E Config

The repo includes `promptbench.local.yaml` configured for local LLMStudio:

- base URL: `http://localhost:1234/v1`
- primary model: `llmstudio/nvidia/nemotron-3-nano-4b`
- fallback model: `llmstudio/essentialai/rnj-1`

Sample artifacts and evals are included under `samples/e2e`.

```bash
# optional if your local endpoint checks for api key
export LLMSTUDIO_API_KEY=dummy

mise x -- uv run -- promptbench review skills sample-skill.md \
  --config promptbench.local.yaml \
  --repo .

mise x -- uv run -- promptbench eval skills sample-skill.md --enhance --loop 3 \
  --concurrency 2 \
  --continuous --continuous-max-rounds 3 \
  --config promptbench.local.yaml \
  --repo .

mise x -- uv run -- promptbench eval-all skills --loop 2 \
  --continuous --continuous-max-rounds 3 \
  --config promptbench.local.yaml \
  --repo .

# opt out of strict mode when running without loaded model
mise x -- uv run -- promptbench eval skills sample-skill.md --enhance --loop 3 \
  --no-require-model-success \
  --config promptbench.local.yaml \
  --repo .

mise x -- uv run -- promptbench report --format markdown \
  --config promptbench.local.yaml \
  --repo .

mise x -- uv run -- promptbench serve --host 127.0.0.1 --port 8080 \
  --config promptbench.local.yaml \
  --repo .
```

## Config highlights

- `objects.defaults.max_line_count` / `max_token_count`
- Per-type overrides in `objects.skills|prompts|agents|tools`
- Per-eval override in `object_limits`
- DB path in `output.database_path`
- `policies.require_model_success` defaults to `true`

Eval loop enhancements:
- `eval` now executes all tests in each eval definition (not just first test)
- best iteration score tracking (`best_iteration`) and stop reason reporting
- `--continuous` plus `--continuous-max-rounds` for iterative improve-until-no-change mode
- `eval-all <artifact_type>` command for aggregate evaluation across discovered targets
- `--output` for `eval` and `eval-all` writes JSON trajectory artifacts
- `workflows.enhance.write_mode: apply` enables in-loop content rewrite attempts
- `--concurrency` allows explicit parallelism; when omitted, concurrency is auto-tuned per provider/base URL
- Provider-specific cap is configurable via `providers.registry.<id>.max_concurrency`

## Reporting + Dashboard

- `promptbench report --format json|markdown`
- Dashboard routes:
  - `/`
  - `/runs`
  - `/runs/<id>`
  - `/artifacts`
  - `/artifacts/<id>`
  - `/metrics`

## Notes

- Review/eval/enhance now use structured output models and `pydantic-ai` runtime paths.
- If model calls fail (e.g., missing API key/network), workflows fall back to deterministic local heuristics and still log run metadata.
