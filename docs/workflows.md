# Workflows

Three core workflows execute when you run `review`, `eval`, or `eval-all`. Each workflow calls LLM models via a fallback chain and persists all telemetry to the SQLite database.

---

## Review

**Command:** `promptbench review <type> <target>`

**Purpose:** Static validation + LLM-powered feedback on a single artifact.

**Steps:**

1. Create a run record in the database
2. Resolve the artifact file → upsert into artifact table
3. Run type-specific static validation (e.g., frontmatter checks for skills)
4. For each model in the chain (primary → fallbacks):
   - Call review agent with artifact content
   - Parse `ReviewModelOutput` → structured findings list
   - Log prompt, response, and raw response to payload_logs
   - Record model invocation event (success/failure, latency)
   - Break on first success
5. Persist findings to `review_findings` table
6. If `require_model_success=true` and all models failed → mark run as failed
7. Finish run (record duration)

**LLM output model:**

```python
class ReviewFindingOutput(BaseModel):
    severity: str           # "error" | "warning" | "info"
    code: str | None        # Machine-readable finding code
    message: str            # Human-readable description
    suggestion: str | None  # Recommended fix
    location: str | None    # File location reference
```

**Fallback:** If all models fail, static validation findings are still recorded and the run completes with `model_success=false`.

---

## Eval

**Command:** `promptbench eval <type> <target> [--enhance] [--loop N] [--continuous]`

**Purpose:** Score an artifact against a test suite, optionally iterating until it passes or converges.

**Loop structure (nested):**

```
for each EvalDefinition:
  for each continuous round (if --continuous):
    for iteration in range(loop):
      ThreadPoolExecutor (concurrency N):
        for each test in definition:
          _evaluate_single_test()
      aggregate scores → stop_reason
      if enhance and not passed:
        generate_enhancement_suggestions()
    if score improved: continue rounds
```

**Per-test evaluation steps:**

1. Select prompt from test (random if multiple prompts defined)
2. Resolve effective size limits (3-layer merge)
3. Check artifact within limits → `size_cap_exceeded` if not
4. Call eval agent → `EvalModelOutput`
5. Persist: score, metrics, assertions to database

**LLM output model:**

```python
class EvalModelOutput(BaseModel):
    score: float                        # 0.0–1.0
    metrics: list[EvalMetricOutput]     # Named metric scores with optional weights
    assertions_passed: list[str]
    assertions_failed: list[str]
```

**Score aggregation:** Mean of all test scores in the iteration.

**Stop reasons:**

| Reason | Condition |
|---|---|
| `threshold_met` | Aggregate score ≥ `workflows.eval.pass_threshold` |
| `max_iterations` | Reached `--loop N` iterations |
| `size_cap_exceeded` | Artifact exceeds size limits |
| `model_invocation_failed` | All models failed + `require_model_success=true` |

**Fallback scoring:** When all models fail, a simple keyword-overlap heuristic produces a fallback score so the run still completes.

---

## Enhance

**Purpose:** Generate improvement suggestions and optionally rewrite the artifact. Called automatically within eval when `--enhance` and the artifact hasn't passed.

**Two-stage pipeline:**

### Stage 1 — Suggestion pre-pass

- Call suggestion agent with artifact content + eval report context
- Parse `SuggestionListOutput` → `suggestions: list[str]`
- Log to DB with `stage="enhance_suggest"`

### Stage 2 — Rewrite candidate generation

- Call enhance agent with artifact content + stage-1 suggestions + report context
- Parse `EnhanceModelOutput` → `suggestions`, `revised_content`
- Log to DB with `stage="enhance_rewrite"`

**LLM output models:**

```python
class SuggestionListOutput(BaseModel):
    suggestions: list[str]

class EnhanceModelOutput(BaseModel):
    suggestions: list[str]
    revised_content: str | None   # Full rewritten artifact text
```

**Write behavior** (controlled by `workflows.enhance.write_mode`):

| Mode | Behavior |
|---|---|
| `suggestion-only` | Suggestions recorded; artifact file unchanged |
| `apply` | If `revised_content` is non-null and differs from current, overwrite artifact file |

**Hardcoded fallback suggestions** (injected when no model produces output and content is sparse):
- "Add meaningful content."
- "Add more explicit examples and constraints."
- "Tighten wording and add concrete acceptance criteria."

---

## Model Chain Execution

All three workflows share the same fallback pattern:

```python
for provider in resolved_model_chain:
    try:
        with provider_openai_env(provider):
            result = agent.run_sync(prompt, model=provider.model_name)
        return parse(result), success=True
    except Exception as e:
        log_invocation_event(provider, success=False, error=e)
        continue
# All failed → use heuristic fallback
```

The `provider_openai_env` context manager sets `OPENAI_BASE_URL` and `OPENAI_API_KEY` from the provider config, then restores the previous values on exit.

---

## Telemetry Written Per Run

Every workflow run writes to these tables:

| Table | Content |
|---|---|
| `runs` | Run kind, status, start/end time, error message |
| `run_context` | Config hash, concurrency details, verbosity |
| `run_artifacts` | Which artifact(s) were evaluated |
| `artifact_measurements` | Line count, token estimate, limit check result |
| `model_invocation_events` | Per-attempt: latency, tokens, cost estimate, error type |
| `payload_logs` | Full prompt + response text (SHA256 hashed) |
| `review_findings` | (review only) Structured findings |
| `eval_cases` | (eval only) Per-test score, prompt used |
| `assertion_results` | (eval only) Per-assertion pass/fail |
| `metric_results` | (eval only) Per-metric weighted score |
| `loop_progress` | (eval only) Per-iteration score + stop reason |
| `enhancement_suggestions` | (enhance only) Suggestions + applied flag |
