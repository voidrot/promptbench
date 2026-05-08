# CLI Reference

All commands share common flags (`--config`, `--repo`). Run `promptbench <command> --help` for inline help.

---

## Global Patterns

| Flag | Default | Description |
|---|---|---|
| `--config` | `promptbench.yaml` | Path to config file |
| `--repo` | `.` | Project root directory |

---

## `init`

Initialize a default config file.

```
promptbench init [OPTIONS]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--config` | Path | `promptbench.yaml` | Output path |
| `--force` | bool | False | Overwrite existing file |

Writes a template `promptbench.yaml` with sensible defaults. Safe to re-run without `--force` (exits early if file exists).

---

## `upgrade`

Upgrade an existing config file to the latest schema version, preserving existing values and filling missing defaults.

```
promptbench upgrade [OPTIONS]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--config` | Path | `promptbench.yaml` | Config file to upgrade |

Reports applied changes and deprecation warnings.

---

## `review`

Review a single artifact for issues.

```
promptbench review <artifact_type> <target> [OPTIONS]
```

**Arguments:**

| Argument | Values |
|---|---|
| `artifact_type` | `skills` `prompts` `agents` `tools` `instructions` |
| `target` | Artifact filename (relative to artifact root, or absolute path) |

**Flags:**

| Flag | Type | Default | Description |
|---|---|---|---|
| `--require-model-success` / `--no-require-model-success` | bool | from config | Fail if no model call succeeded |
| `--randomize-model` / `--no-randomize-model` | bool | from config | Override model-order shuffling for `review`/`judge` workflows |
| `--model-random-seed` | int | from config | Deterministic seed for model shuffling |
| `--log-verbosity` | str | from config | `quiet` `normal` `debug` `trace` |

**Output:** Prints findings (severity, message, suggestion, location). Exits non-zero if model required and unavailable.

---

## `eval`

Evaluate an artifact against its eval suite.

```
promptbench eval <artifact_type> <target> [OPTIONS]
```

**Arguments:**

| Argument | Values |
|---|---|
| `artifact_type` | `skills` `prompts` `agents` `tools` `instructions` |
| `target` | Artifact filename |

**Flags:**

| Flag | Type | Default | Description |
|---|---|---|---|
| `--enhance` | bool | False | Run enhancement loop after each iteration |
| `--loop N` | int | from config | Max eval iterations per round |
| `--concurrency N` | int | auto | Parallel test workers (auto-tuned if omitted) |
| `--continuous` | bool | False | Keep re-running rounds while score improves |
| `--continuous-max-rounds N` | int | 6 | Hard cap on continuous rounds (max 6) |
| `--require-model-success` / `--no-require-model-success` | bool | True | Fail if model call errors |
| `--randomize-model` / `--no-randomize-model` | bool | from config | Override model-order shuffling for `eval`/`judge`/`enhance` workflows |
| `--model-random-seed` | int | from config | Deterministic seed for model shuffling |
| `--log-verbosity` | str | from config | `quiet` `normal` `debug` `trace` |
| `--output FILE` | Path | auto | Write JSON trajectory to file |

**Auto output naming:** `.promptbench/reports/eval-<type>-<UTC>.json`

**Stop reasons:**

| Reason | Meaning |
|---|---|
| `threshold_met` | Score ≥ pass_threshold |
| `max_iterations` | Loop limit reached |
| `size_cap_exceeded` | Artifact exceeds configured limits |
| `model_invocation_failed` | All models in chain failed |

---

## `eval-all`

Discover and evaluate all artifacts of a type.

```
promptbench eval-all <artifact_type> [OPTIONS]
```

**Arguments:**

| Argument | Values |
|---|---|
| `artifact_type` | `skills` `prompts` `agents` `tools` `instructions` |

Accepts the same flags as `eval` (minus `target` — discovers all targets automatically).

**Auto output naming:** `.promptbench/reports/eval-all-<type>-<UTC>.json`

**Output:** Aggregate summary: total / passed / failed / errored runs.

---

## `eval-generate`

Generate an eval definition for a single artifact target.

```
promptbench eval-generate <artifact_type> <target> [OPTIONS]
```

**Arguments:**

| Argument | Values |
|---|---|
| `artifact_type` | `skills` `prompts` `agents` `tools` `instructions` |
| `target` | Artifact filename or absolute path |

**Flags:**

| Flag | Type | Default | Description |
|---|---|---|---|
| `--name` | str | artifact stem | Base name for generated eval file |
| `--randomize-model` / `--no-randomize-model` | bool | from config | Override model-order shuffling for `eval`/`judge` workflows |
| `--model-random-seed` | int | from config | Deterministic seed for model shuffling |
| `--log-verbosity` | str | from config | `quiet` `normal` `debug` `trace` |

**Output:** writes one generated eval definition to `.promptbench/evals/*.eval.yaml`.

---

## `eval-merge`

Merge multiple targets of the same artifact type, seed initial eval tests, and run `eval` with loop=10.

```
promptbench eval-merge <artifact_type> <target...> [OPTIONS]
```

**Arguments:**

| Argument | Values |
|---|---|
| `artifact_type` | `skills` `prompts` `agents` `tools` `instructions` |
| `target...` | Two or more targets of the same type |

**Flags:**

| Flag | Type | Default | Description |
|---|---|---|---|
| `--name` | str | first target stem | Base name for merged artifact/eval files |
| `--concurrency N` | int | auto | Parallel test workers for follow-up eval |
| `--require-model-success` / `--no-require-model-success` | bool | True | Fail if model call errors |
| `--randomize-model` / `--no-randomize-model` | bool | from config | Override model-order shuffling for `eval`/`judge`/`enhance` workflows |
| `--model-random-seed` | int | from config | Deterministic seed for model shuffling |
| `--log-verbosity` | str | from config | `quiet` `normal` `debug` `trace` |

**Output:**
- Writes merged artifact under `<artifact_root>/_merged/`
- Writes generated eval definition under `.promptbench/evals/`
- Executes eval immediately with `loop=10`

---

## `report`

Print a summary of all runs from the database.

```
promptbench report [OPTIONS]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--format` | str | `json` | `json` or `markdown` |
| `--since` | str | — | ISO date filter (reserved, not yet active) |

Aggregates: run counts, model failure stats, concurrency telemetry, recent events.

---

## `serve`

Start the local web dashboard.

```
promptbench serve [OPTIONS]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--host` | str | `127.0.0.1` | Bind address |
| `--port` | int | `8080` | Port |

Launches Flask dev server. See [dashboard.md](dashboard.md) for route reference.

---

## Log Verbosity Levels

| Level | What is logged |
|---|---|
| `quiet` | Errors only |
| `normal` | Run summary, scores, findings |
| `debug` | Model chain resolution, DB operations |
| `trace` | Full prompt/response payloads |
