# Configuration Reference

PromptBench is configured via a YAML file (default: `promptbench.yaml`). Pass `--config <path>` to any command to use a different file.

Run `promptbench init` to generate a starter config.

---

## Environment Variable Interpolation

String values support env var substitution:

```yaml
api_key_env: OPENAI_API_KEY        # looked up at runtime
base_url: ${CUSTOM_API_BASE_URL}   # explicit ${VAR} syntax
```

---

## Full Schema

### `version`

```yaml
version: 2
```

Schema version. Current version is `2`.

Use `promptbench upgrade` to migrate older config files and add newly introduced defaults.

---

### `project`

```yaml
project:
  name: my-project     # Project identifier (default: "project")
  root: .              # Project root path (default: ".")
```

`root` is resolved relative to the directory containing the config file.

---

### `objects`

Size limits applied to artifacts before evaluation.

```yaml
objects:
  defaults:
    max_line_count: 200        # Global line limit (null = no limit)
    max_token_count: 4096      # Global token limit (null = no limit)
  skills:
    max_line_count: 150        # Overrides defaults for skills only
  prompts:
    max_token_count: 2048
  agents: {}
  tools: {}
  instructions: {}
```

**Resolution order (highest priority wins):** eval-definition `object_limits` → artifact-type section → `defaults`.

---

### `artifacts`

Paths and per-type settings for each artifact category.

```yaml
artifacts:
  skills:
    root_path: skills/              # Path relative to project.root
    improve_references: false       # Enable reference improvement in enhance
    improve_scripts: false          # Enable script improvement in enhance
    evals: []                       # Inline eval definitions (see workflows.eval)
  prompts:
    root_path: prompts/
  agents:
    root_path: agents/
  tools:
    root_path: tools/
  instructions:
    root_path: instructions/
```

---

### `providers`

Model provider configuration.

```yaml
providers:
  default_kind: openai-compatible

  defaults:
    timeout_seconds: 60
    max_retries: 3
    temperature: 0.2

  registry:
    openai:
      kind: openai-compatible
      base_url: https://api.openai.com/v1
      api_key_env: OPENAI_API_KEY
      max_concurrency: 5            # Optional; overrides auto-detection

    lmstudio:
      kind: openai-compatible
      base_url: http://localhost:1234/v1
      api_key_env: LLMSTUDIO_API_KEY
      max_concurrency: 2

  workflows:
    review:
      provider_kind: openai-compatible
      model: openai/gpt-4o-mini           # Format: <registry_key>/<model_name>
      fallback_models:
        - openai/gpt-3.5-turbo
      randomize_model: false
    eval:
      provider_kind: openai-compatible
      model: openai/gpt-4o-mini
      fallback_models: []
      randomize_model: false
    judge:
      provider_kind: openai-compatible
      model: openai/gpt-4o-mini
      fallback_models:
        - openai/gpt-3.5-turbo
      randomize_model: false
    enhance:
      provider_kind: openai-compatible
      model: openai/gpt-4o
      fallback_models:
        - openai/gpt-4o-mini
      randomize_model: false
```

**Model ID format:** `<registry_key>/<model_name>` — the registry key must match a key in `providers.registry`.

**Workflow model routing defaults:**
- `review` workflow uses `providers.workflows.review`, then falls back to `providers.workflows.judge`
- `eval` scoring uses `providers.workflows.judge`, then falls back to `providers.workflows.eval`
- `enhance` uses `providers.workflows.enhance`, then falls back to `providers.workflows.judge`

When `randomize_model: true`, PromptBench shuffles `[model + fallback_models]` before attempts.

**Concurrency resolution order:**
1. `--concurrency` CLI flag
2. `providers.registry.<id>.max_concurrency`
3. Localhost auto-cap: 2
4. Remote auto-cap: 1
5. `policies.max_workers`

All values clamped to `[1, 8]`.

---

### `workflows`

Per-workflow behavior settings.

```yaml
workflows:
  review:
    enabled: true
    max_findings: 25              # Max issues to surface

  eval:
    enabled: true
    metrics:                      # Metrics the model is asked to score
      - clarity
      - specificity
      - safety
    pass_threshold: 0.8           # Score [0.0–1.0] required to pass
    definition_mode: discover     # "discover" or "inline"
    discover_path: evals/         # Relative to project.root; scans *.eval.yaml
    inline: []                    # Inline EvalDefinition objects

  enhance:
    enabled: true
    write_mode: suggestion-only   # "suggestion-only" or "apply"
    run_in_eval_loop: true        # Run enhancement inside eval iterations
```

**`enhance.write_mode`:**
- `suggestion-only` — generate suggestions, do not modify artifact
- `apply` — attempt to write revised content back to the artifact file

---

### `output`

```yaml
output:
  database_path: .promptbench/promptbench.db   # SQLite database location
  overwrite: false                              # Overwrite existing reports
  reports_dir: .promptbench/reports            # JSON trajectory output directory
```

---

### `policies`

```yaml
policies:
  fail_on_severity: error         # Min finding severity that fails a review run
  fail_on_score_below: 0.7        # Eval score below this = failed run
  max_workers: 1                  # Default thread pool size
  require_model_success: true     # Fail run if no model call succeeded
  log_verbosity: normal           # quiet | normal | debug | trace
  model_random_seed: null         # Optional deterministic seed for model randomization
```

**`require_model_success`:** When `true` (default), a run is marked failed if every model in the chain errored. Set `false` with `--no-require-model-success` to allow runs without a live model (useful for local testing with heuristic fallbacks).

---

## Eval Definition Schema

Eval definitions can appear inline in config or as `*.eval.yaml` files.

```yaml
# skills/my-skill.eval.yaml
id: basic-eval
artifact_type: skills
target: my-skill.md
model: openai/gpt-4o-mini           # Optional; overrides workflows.eval.model
fallback_models:
  - openai/gpt-3.5-turbo
randomize_model: false
object_limits:
  max_line_count: 100               # Per-eval limit override
tests:
  - id: test-1
    prompts:
      - id: english
        text: "Evaluate this skill for clarity."
      - id: spanish
        text: "Evalúa esta habilidad en cuanto a claridad."
    model: openai/gpt-4o            # Per-test model override
    randomize_model: null           # Per-test randomization override (null uses eval definition)
    inputs:
      context: some-value
    expected:
      has_examples: true
    references:
      - "Skills should include concrete examples."
    object_limits:
      max_token_count: 2000         # Per-test limit override
```

**Discovery:** PromptBench discovers eval files from:
1. `config.workflows.eval.inline` list
2. `config.artifacts.<type>.evals` list
3. `<discover_path>/*.eval.yaml`
4. `<artifact_root>/*.eval.yaml`

Definitions are deduplicated by `(artifact_type, target, id)`.
