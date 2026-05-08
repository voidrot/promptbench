from pathlib import Path

from promptbench.config.loader import load_config


def test_load_config(tmp_path: Path) -> None:
    config_path = tmp_path / "promptbench.yaml"
    config_path.write_text(
        """
version: 1
project:
  name: test
  root: .
objects:
  defaults:
    max_line_count: 100
    max_token_count: 200
  skills: {}
  prompts: {}
  agents: {}
  tools: {}
artifacts:
  prompts:
    root_path: prompts/
  skills:
    root_path: skills/
  agents:
    root_path: agents/
  tools:
    root_path: tools/
providers:
  default_kind: openai-compatible
  defaults:
    timeout_seconds: 60
    max_retries: 3
    temperature: 0.2
  registry: {}
  workflows: {}
workflows:
  review:
    enabled: true
    max_findings: 25
  eval:
    enabled: true
    metrics: []
    pass_threshold: 0.8
    definition_mode: discover
    discover_path: evals/
    inline: []
  enhance:
    enabled: true
    write_mode: suggestion-only
    run_in_eval_loop: true
output:
  database_path: .promptbench/promptbench.db
  overwrite: false
  reports_dir: .promptbench/reports
policies:
  fail_on_severity: error
  fail_on_score_below: 0.7
  max_workers: 1
  require_model_success: true
""",
        encoding="utf-8",
    )
    cfg = load_config(config_path)
    assert cfg.objects.defaults.max_line_count == 100
    assert cfg.policies.require_model_success is True
    assert cfg.policies.log_verbosity == "normal"
