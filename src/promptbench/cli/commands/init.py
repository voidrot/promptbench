from __future__ import annotations

from pathlib import Path

import typer


DEFAULT_CONFIG = """version: 2

project:
  name: "my-project"
  root: "."

objects:
  defaults:
    max_line_count: 800
    max_token_count: 12000
  skills:
    max_line_count: 1200
  prompts:
    max_token_count: 8000
  agents: {}
  tools: {}
  instructions: {}

artifacts:
  prompts:
    root_path: "prompts/"
  skills:
    root_path: "skills/"
    improve_references: true
    improve_scripts: true
  agents:
    root_path: "agents/"
  tools:
    root_path: "tools/"
  instructions:
    root_path: "instructions/"

providers:
  default_kind: openai-compatible
  defaults:
    timeout_seconds: 60
    max_retries: 3
    temperature: 0.2
  registry:
    openai:
      kind: openai-compatible
      base_url: "https://api.openai.com/v1"
      api_key_env: "OPENAI_API_KEY"
      max_concurrency: 1
  workflows:
    review:
      provider_kind: openai
      model: "openai/gpt-4.1-mini"
      fallback_models: []
      randomize_model: false
    eval:
      provider_kind: openai
      model: "openai/gpt-4.1-mini"
      fallback_models: []
      randomize_model: false
    judge:
      provider_kind: openai
      model: "openai/gpt-4.1-mini"
      fallback_models: []
      randomize_model: false
    enhance:
      provider_kind: openai
      model: "openai/gpt-4.1-mini"
      fallback_models: []
      randomize_model: false

workflows:
  review:
    enabled: true
    max_findings: 25
  eval:
    enabled: true
    metrics: ["clarity", "specificity", "safety", "structure", "testability", "reproducibility"]
    pass_threshold: 0.8
    definition_mode: "discover"
    discover_path: "evals/"
    inline: []
  enhance:
    enabled: true
    write_mode: "apply"
    run_in_eval_loop: true

output:
  database_path: ".promptbench/promptbench.db"
  overwrite: false
  reports_dir: ".promptbench/reports"

policies:
  fail_on_severity: "error"
  fail_on_score_below: 0.7
  max_workers: 1
  require_model_success: true
  model_random_seed: null
  log_verbosity: "normal"
"""


def init_command(config: Path = Path("promptbench.yaml"), force: bool = False) -> None:
    if config.exists() and not force:
        raise typer.BadParameter(
            f"Config already exists at {config}. Use --force to overwrite."
        )
    config.write_text(DEFAULT_CONFIG, encoding="utf-8")
    typer.echo(f"Wrote {config}")
