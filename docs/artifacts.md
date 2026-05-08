# Artifacts

Artifacts are the files PromptBench evaluates — skills, prompts, agents, tools, or instructions. Each is a text artifact resolved from the configured root path.

---

## Artifact Types

| Type | CLI name | Default root path |
|---|---|---|
| Skills | `skills` | `skills/` |
| Prompts | `prompts` | `prompts/` |
| Agents | `agents` | `agents/` |
| Tools | `tools` | `tools/` |
| Instructions | `instructions` | `instructions/` |

Root paths are relative to `project.root` and configurable per type in `artifacts.<type>.root_path`.

---

## Skill Format

Skills are the primary artifact type with the strictest validation rules.

```markdown
---
name: my-skill
description: One-line description of what this skill does.
---

# My Skill

## Goal
What the skill is trying to accomplish.

## Steps
1. Step one.
2. Step two.

## Examples
- Input: ...
  Output: ...
```

**Required frontmatter fields:**

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Machine-readable identifier |
| `description` | Yes | Human-readable summary |

**Validation rules** (checked by `validators/skills_spec.py`):

| Rule | Finding code |
|---|---|
| File must start with `---` (YAML frontmatter delimiter) | `missing_frontmatter` |
| Content must include `name:` | `missing_name` |
| Content must include `description:` | `missing_description` |

Validation runs before any model calls during `review`.

Note: instruction artifacts currently use generic text handling (no dedicated static validator yet).

---

## Artifact Resolution

Target argument to `review` / `eval` is resolved in this order:

1. **Absolute path** — used as-is if the path is absolute
2. **Relative to artifact root** — `<project.root>/<artifact_root_path>/<target>`

**Examples:**

```bash
# Resolved as: <project_root>/skills/my-skill.md
promptbench eval skills my-skill.md

# Resolved as absolute path
promptbench eval skills /home/user/project/skills/my-skill.md
```

**Errors:**
- `FileNotFoundError` — file not found at resolved path
- `IsADirectoryError` — target resolves to a directory (pass a file, not a directory)

---

## ArtifactDocument

Internal dataclass populated by the resolver:

| Field | Type | Description |
|---|---|---|
| `artifact_type` | str | Artifact type name |
| `name` | str | Filename without extension |
| `path` | Path | Absolute file path |
| `content` | str | Full file text |
| `line_count` | int | Number of lines |
| `token_count_estimate` | int | `len(content) // 4` (rough estimate) |

---

## Size Limits

Artifacts are checked against size limits before eval runs. Limits are resolved in this order (highest priority first):

1. `object_limits` on the specific `EvalTest`
2. `object_limits` on the `EvalDefinition`
3. `objects.<artifact_type>` section in config
4. `objects.defaults` in config

If `line_count > max_line_count` or `token_count_estimate > max_token_count`, the eval iteration stops with `stop_reason: size_cap_exceeded`.

---

## Eval Definition Files

Each artifact can have associated eval definitions in `*.eval.yaml` files.

**Discovery locations (in order):**
1. `config.workflows.eval.inline` list
2. `config.artifacts.<type>.evals` inline list
3. `<discover_path>/*.eval.yaml` (default: `evals/`)
4. `<artifact_root>/*.eval.yaml`

Definitions are deduplicated by `(artifact_type, target, id)`.

**Minimal eval definition:**

```yaml
id: my-eval
artifact_type: skills
target: my-skill.md
tests:
  - id: basic
    prompts:
      - text: "Evaluate this skill for clarity and completeness."
```

See [configuration.md](configuration.md) for the full eval definition schema.

---

## Sample Artifact

`samples/e2e/skills/sample-skill.md` — included for local LLMStudio end-to-end testing:

```markdown
---
name: sample-skill
description: A local test skill used for PromptBench e2e execution.
---

# Sample Skill

## Goal
Provide a deterministic sample artifact for local PromptBench testing.

## Steps
1. Read the input carefully.
2. Return concise and structured output.
3. Include one concrete example.
```
