# Architecture

## Overview

PromptBench is a Python CLI that evaluates and iteratively improves agent artifacts (skills, prompts, agents, tools, instructions) against LLM-backed eval suites. It persists all run telemetry to SQLite and exposes a local Flask dashboard for browsing results.

## Module Map

```
src/promptbench/
├── cli/                  Entry point; Typer app + 7 commands
│   └── commands/         One module per command (init, review, eval, eval_all, eval_merge, report, serve)
├── config/               YAML loading and Pydantic schema
├── artifacts/            Artifact resolution and dataclasses
├── evals/                Eval definition loading and prompt selection
├── provider/             Model ID parsing and provider/concurrency resolution
├── workflows/            Review, eval, enhance business logic + Pydantic LLM models
├── validators/           Artifact-type-specific validation rules (skills)
├── reporting/            SQLModel ORM, DB init, repository query layer
└── web/                  Flask dashboard app
```

## Dependency Flow

```
CLI command
  │
  ├─► config/loader.py        Load + validate YAML → PromptBenchConfig
  ├─► reporting/database.py   Init SQLite engine
  ├─► reporting/repository.py Open session
  │
  └─► workflows/<name>.py
        │
        ├─► artifacts/resolver.py    Locate + read artifact file
        ├─► evals/loader.py          Discover eval definitions
        ├─► evals/selection.py       Pick prompt from test
        ├─► provider/runtime.py      Resolve model chain + concurrency
        ├─► validators/              Type-specific static checks
        ├─► [pydantic-ai agent]      Call LLM → structured output
        └─► reporting/repository.py  Persist every event, metric, finding
```

## Data Flow: Eval

```
eval command
  └─ run_eval()
       └─ for each EvalDefinition:
            └─ for each continuous round:
                 └─ _run_definition_round()
                      └─ for each iteration:
                           └─ ThreadPoolExecutor (concurrency N)
                                └─ _evaluate_single_test() per test
                                     ├─ resolve artifact + limits
                                     ├─ call LLM → EvalModelOutput
                                     │    score, metrics, assertions
                                     ├─ persist to DB
                                     └─ if enhance=true and not passed:
                                          └─ generate_enhancement_suggestions()
                                               ├─ Stage 1: suggestion pre-pass
                                               └─ Stage 2: rewrite candidate
```

## Concurrency Resolution

Priority order (highest wins):

1. `--concurrency` CLI flag
2. `providers.registry.<id>.max_concurrency` from config
3. Localhost provider auto-cap: 2
4. Remote provider auto-cap: 1
5. `policies.max_workers` from config

All values are clamped to `[1, 8]`.

## Model Chain Fallback

All workflow LLM calls iterate a model chain:

```
[primary_model, ...fallback_models]
```

Routing preference by stage:

- review stage: `review` chain, then `judge` chain
- eval scoring stage: `judge` chain, then `eval` chain
- enhance stages: `enhance` chain, then `judge` chain

When `randomize_model` is enabled for the selected workflow chain, ordering is shuffled before attempts. `policies.model_random_seed` enables deterministic shuffles.

On each model: try → structured output parse → record invocation event.
First success wins. Chain continues on error. If all fail, workflow uses deterministic local heuristics and records failure.

## Structured Output Models

| Model | Used in | Fields |
|---|---|---|
| `ReviewModelOutput` | review workflow | `findings[]` (severity, code, message, suggestion, location) |
| `EvalModelOutput` | eval workflow | `score`, `metrics[]`, `assertions_passed[]`, `assertions_failed[]` |
| `EnhanceModelOutput` | enhance stage 2 | `suggestions[]`, `revised_content` |
| `SuggestionListOutput` | enhance stage 1 | `suggestions[]` |

## Persistence Schema

14 SQLite tables (managed via SQLModel):

| Table | Purpose |
|---|---|
| `artifacts` | Tracked artifact identity + content hash |
| `runs` | Root run records (kind, status, timing) |
| `run_artifacts` | Run ↔ artifact join |
| `run_context` | Per-run config snapshot (concurrency, verbosity, etc.) |
| `model_invocations` | Summary invocation records |
| `model_invocation_events` | Detailed per-attempt events with latency + cost |
| `payload_logs` | Full prompt/response text (hashed, truncation-flagged) |
| `eval_cases` | Per-test eval results (score, pass/fail, prompt used) |
| `assertion_results` | Individual assertion outcomes |
| `metric_results` | Weighted metric scores |
| `review_findings` | Structured review findings |
| `loop_progress` | Per-iteration score + stop reason |
| `artifact_measurements` | Line count, token estimate, limit check |
| `enhancement_suggestions` | Generated suggestions + applied flag |
