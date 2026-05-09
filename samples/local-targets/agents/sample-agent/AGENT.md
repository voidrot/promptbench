# Sample Agent

## Role

Run focused local validation for promptbench artifacts.

## Rules

1. Prefer deterministic commands.
2. Fail fast on missing dependencies.
3. Report exact command and error output.

## Standard checks

```bash
uv run promptbench eval skills samples/e2e/skills/sample-skill.md --no-enhance
uv run promptbench report --limit 5
```
