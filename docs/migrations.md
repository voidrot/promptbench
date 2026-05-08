# Config Migrations

PromptBench supports config schema migrations via the `upgrade` command.

## Command

```bash
promptbench upgrade --config promptbench.yaml
```

The command:

- Reads your existing YAML config
- Migrates from older versions to the latest schema
- Preserves existing values
- Adds missing defaults for newly introduced settings
- Writes the upgraded config back to disk
- Prints warnings for deprecated settings

## Current Versions

- Latest supported config version: `2`
- Migration supported: `1 -> 2`

## `1 -> 2` Changes

- Adds `objects.instructions`
- Adds `artifacts.instructions.root_path`
- Adds `providers.workflows.judge` chain defaults
- Adds `providers.workflows.<review|eval|enhance>.randomize_model` defaults
- Adds `policies.model_random_seed`
- Sets `version: 2`

## Deprecation Warnings

`upgrade` emits warnings for settings that still work but are discouraged due to new routing behavior.

Current warning set includes:

- `providers.workflows.review.provider_kind`
- `providers.workflows.eval.provider_kind`

These warnings are advisory and do not block loading.
