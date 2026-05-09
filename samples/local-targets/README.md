# Local Target Samples

This folder provides directory-based sample targets for manual local testing.

## Skill directory target

- Target path: `samples/local-targets/skills/mise`
- Contains `SKILL.md` and `references/`

## Agent directory target

- Target path: `samples/local-targets/agents/sample-agent`
- Contains `AGENT.md`

## Quick checks

```bash
promptbench eval-generate skills samples/local-targets/skills/mise
promptbench eval-generate agents samples/local-targets/agents/sample-agent
```
