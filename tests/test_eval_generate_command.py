from __future__ import annotations

from pathlib import Path

import pytest

from promptbench.cli.commands import eval_generate
from promptbench.config.schema import ArtifactType, EvalTest


def _write_config(path: Path) -> None:
    path.write_text(
        """
version: 2
project:
  name: test
  root: .
objects:
  defaults: {}
  skills: {}
  prompts: {}
  agents: {}
  tools: {}
  instructions: {}
artifacts:
  prompts:
    root_path: prompts/
  skills:
    root_path: skills/
  agents:
    root_path: agents/
  tools:
    root_path: tools/
  instructions:
    root_path: instructions/
providers:
  default_kind: openai-compatible
  defaults:
    timeout_seconds: 60
    max_retries: 3
    temperature: 0.2
  registry:
    openai:
      kind: openai-compatible
      base_url: http://localhost:1234/v1
      api_key_env: OPENAI_API_KEY
  workflows:
    eval:
      model: openai/mock
      randomize_model: false
    judge:
      model: openai/mock
      randomize_model: false
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
  require_model_success: false
  model_random_seed: null
""",
        encoding="utf-8",
    )


def test_eval_generate_command_creates_eval_for_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path
    (repo_root / "skills").mkdir(parents=True, exist_ok=True)
    (repo_root / "skills" / "a.md").write_text("alpha\n", encoding="utf-8")
    config_path = repo_root / "promptbench.yaml"
    _write_config(config_path)

    monkeypatch.setattr(
        eval_generate,
        "generate_eval_seed_tests",
        lambda **_kwargs: [
            EvalTest(id="t1", prompt="p1"),
            EvalTest(id="t2", prompt="p2"),
            EvalTest(id="t3", prompt="p3"),
        ],
    )

    eval_generate.eval_generate_command(
        artifact_type=ArtifactType.SKILLS,
        target="a.md",
        name="seeded",
        config=config_path,
        repo=repo_root,
    )

    eval_files = list((repo_root / ".promptbench" / "evals").glob("seeded-*.eval.yaml"))
    assert len(eval_files) == 1
    text = eval_files[0].read_text(encoding="utf-8")
    assert "artifact_type: skills" in text
    assert "target: a.md" in text
    assert "id: seed-skills-" in text
    assert "prompt: p1" in text
