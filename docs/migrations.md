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
- Removes deprecated `providers.workflows.<review|eval|judge|enhance>.provider_kind`
- Sets `version: 2`

## Deprecation Warnings

`upgrade` emits warnings for deprecated settings.

Current warning set includes:

- `providers.workflows.review.provider_kind`
- `providers.workflows.eval.provider_kind`
- `providers.workflows.judge.provider_kind`
- `providers.workflows.enhance.provider_kind`

These warnings are advisory and do not block loading. The upgrade process also removes these keys from migrated files.
