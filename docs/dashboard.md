# Dashboard

PromptBench includes a local Flask web dashboard for browsing runs, artifacts, and metrics.

## Starting the Dashboard

```bash
promptbench serve
# or with options:
promptbench serve --host 127.0.0.1 --port 8080 --config promptbench.yaml
```

Default: `http://127.0.0.1:8080`

---

## Routes

### `GET /`

Overview dashboard.

**Shows:**
- Recent runs (last 50)
- Aggregate stats: total runs, completed, failed, pass rate
- Score trend chart (eval case scores over time)
- Stop reason breakdown
- Failing runs list
- Payload log count, model invocation event count

---

### `GET /runs`

Paginated run list.

**Query parameters:**

| Param | Description |
|---|---|
| `page` | Page number (default: 1) |
| `page_size` | Results per page |
| `status` | Filter by run status |
| `kind` | Filter by run kind (`review`, `eval`, `enhance`) |
| `since` | ISO date lower bound |
| `until` | ISO date upper bound |
| `sort` | Sort column |
| `sort_dir` | `asc` or `desc` |

---

### `GET /runs/<run_id>`

Single run detail view.

**Shows:**
- Run metadata (kind, status, duration, trigger)
- Run context (config hash, concurrency source/value, verbosity)
- Review findings (if review run)
- Eval cases with scores, prompts used, pass/fail (if eval run)
- Loop progress (iteration scores + stop reasons)
- Metric results with chart
- Model invocation events (per-attempt: provider, model, latency, tokens, cost estimate)
- Payload logs grouped by prompt/response/error
- Failure diagnostics:
  - Breakdown by error type
  - Breakdown by HTTP status code
  - Breakdown by workflow stage
  - Recent failure events

---

### `GET /artifacts`

Paginated artifact list.

**Query parameters:**

| Param | Description |
|---|---|
| `artifact_type` | Filter by type (`skills`, `prompts`, etc.) |
| `since` | ISO date lower bound |
| `until` | ISO date upper bound |
| `sort` / `sort_dir` | Sort column and direction |

---

### `GET /artifacts/<artifact_id>`

Single artifact detail view.

**Shows:**
- Artifact metadata (type, name, path, content hash)
- Size measurement history (line count, token estimate) as a chart
- Linked runs (all runs that evaluated this artifact)

---

### `GET /metrics`

Paginated metric results across all runs.

**Query parameters:**

| Param | Description |
|---|---|
| `metric_name` | Filter by metric name |
| `since` / `until` | Date range |
| `sort` / `sort_dir` | Sort column and direction |
| `page` / `page_size` | Pagination |

Shows aggregate chart of metric values over time.

---

## API Endpoints

### `GET /api/charts/score-trend`

Returns JSON for the score trend chart.

```json
{
  "labels": ["2024-01-01T12:00:00", "..."],
  "values": [0.72, 0.85, "..."]
}
```

### `GET /api/healthcheck/models`

Checks connectivity to all configured workflow model providers.

```json
{
  "ok": true,
  "checks": [
    {
      "workflow": "eval",
      "provider_id": "openai",
      "model": "gpt-4o-mini",
      "ok": true,
      "status_code": 200,
      "error": null
    }
  ]
}
```

Queries each provider's `/models` endpoint. Useful for verifying API keys and connectivity before a run.
