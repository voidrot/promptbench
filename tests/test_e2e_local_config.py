from pathlib import Path

from promptbench.cli.commands.eval import eval_command
from promptbench.cli.commands.eval_all import eval_all_command
from promptbench.cli.commands.review import review_command
from promptbench.config.schema import ArtifactType
from promptbench.reporting.database import init_database, session_for
from promptbench.reporting.models import Run
from sqlmodel import select


def test_e2e_local_config_paths_and_db(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    # Mirror sample structure
    samples_root = repo / "samples" / "e2e"
    (samples_root / "skills").mkdir(parents=True, exist_ok=True)
    (samples_root / ".promptbench" / "evals").mkdir(parents=True, exist_ok=True)

    (samples_root / "skills" / "sample-skill.md").write_text(
        """---
name: sample-skill
description: sample
---

Hello sample skill.
""",
        encoding="utf-8",
    )

    (samples_root / ".promptbench" / "evals" / "sample-skill.eval.yaml").write_text(
        """
id: sample-skill-eval
artifact_type: skills
target: sample-skill.md
prompt: evaluate this
""",
        encoding="utf-8",
    )

    config = repo / "promptbench.local.yaml"
    config.write_text(
        """
version: 1
project:
  name: local
  root: samples/e2e
objects:
  defaults:
    max_line_count: 1000
    max_token_count: 10000
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
    max_retries: 2
    temperature: 0.2
  registry:
    llmstudio:
      kind: openai-compatible
      base_url: http://localhost:1234/v1
      api_key_env: LLMSTUDIO_API_KEY
  workflows:
    review:
      model: llmstudio/nvidia/nemotron-3-nano-4b
      fallback_models: [llmstudio/essentialai/rnj-1]
      randomize_model: false
    eval:
      model: llmstudio/nvidia/nemotron-3-nano-4b
      fallback_models: [llmstudio/essentialai/rnj-1]
      randomize_model: false
    judge:
      model: llmstudio/essentialai/rnj-1
      fallback_models: [llmstudio/nvidia/nemotron-3-nano-4b]
      randomize_model: false
    enhance:
      model: llmstudio/nvidia/nemotron-3-nano-4b
      fallback_models: [llmstudio/essentialai/rnj-1]
      randomize_model: false
workflows:
  review:
    enabled: true
    max_findings: 25
  eval:
    enabled: true
    metrics: [clarity]
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
policies:
  fail_on_severity: error
  fail_on_score_below: 0.7
  max_workers: 1
  require_model_success: false
  model_random_seed: 7
""",
        encoding="utf-8",
    )

    db_path = samples_root / ".promptbench" / "promptbench.db"
    engine = init_database(db_path)

    review_command(
        artifact_type=ArtifactType.SKILLS,
        target="sample-skill.md",
        config=config,
        repo=repo,
    )
    eval_command(
        artifact_type=ArtifactType.SKILLS,
        target="sample-skill.md",
        enhance=True,
        loop=2,
        concurrency=2,
        output=repo / "eval.json",
        require_model_success=False,
        config=config,
        repo=repo,
    )
    eval_all_command(
        artifact_type=ArtifactType.SKILLS,
        enhance=False,
        loop=1,
        concurrency=2,
        output=repo / "eval-all.json",
        require_model_success=False,
        config=config,
        repo=repo,
    )

    output = capsys.readouterr().out
    assert "[PASSED]" in output
    assert "stop:" in output
    assert "concurrency:" in output

    assert db_path.exists()

    with session_for(engine) as session:
        run_count = len(session.exec(select(Run)).all())
    assert run_count >= 2
    assert (repo / "eval.json").exists()
    assert (repo / "eval-all.json").exists()
