from pathlib import Path

from promptbench.config.loader import load_config
from promptbench.config.schema import ArtifactType
from promptbench.evals.loader import load_eval_definitions


def test_loader_deduplicates_and_matches_type(tmp_path: Path) -> None:
    repo_root = tmp_path
    (repo_root / "skills").mkdir(parents=True, exist_ok=True)
    (repo_root / "prompts").mkdir(parents=True, exist_ok=True)
    (repo_root / "instructions").mkdir(parents=True, exist_ok=True)
    (repo_root / ".promptbench" / "evals").mkdir(parents=True, exist_ok=True)

    (repo_root / ".promptbench" / "evals" / "a.eval.yaml").write_text(
        """
id: shared
artifact_type: skills
target: x.md
prompt: one
""",
        encoding="utf-8",
    )
    (repo_root / "skills" / "a.eval.yaml").write_text(
        """
id: shared
artifact_type: skills
target: x.md
prompt: two
""",
        encoding="utf-8",
    )
    (repo_root / "skills" / "b.eval.yaml").write_text(
        """
id: only-skills
artifact_type: skills
target: y.md
prompt: two
""",
        encoding="utf-8",
    )
    (repo_root / "prompts" / "c.eval.yaml").write_text(
        """
id: prompt-eval
artifact_type: prompts
target: p.md
prompt: p
""",
        encoding="utf-8",
    )

    cfg_path = repo_root / "promptbench.yaml"
    cfg_path.write_text(
        """
version: 1
project:
  name: t
  root: .
objects:
  defaults: {}
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
  require_model_success: false
""",
        encoding="utf-8",
    )

    cfg = load_config(cfg_path)
    defs = load_eval_definitions(repo_root, cfg, artifact_type=ArtifactType.SKILLS)

    ids = sorted(d.id for d in defs)
    assert ids == ["only-skills", "shared"]


def test_loader_discovers_instruction_evals(tmp_path: Path) -> None:
    repo_root = tmp_path
    (repo_root / "instructions").mkdir(parents=True, exist_ok=True)
    (repo_root / ".promptbench" / "evals").mkdir(parents=True, exist_ok=True)

    (repo_root / ".promptbench" / "evals" / "inst.eval.yaml").write_text(
        """
id: instruction-eval
artifact_type: instructions
target: playbook.md
prompt: validate instruction quality
""",
        encoding="utf-8",
    )

    cfg_path = repo_root / "promptbench.yaml"
    cfg_path.write_text(
        """
version: 1
project:
  name: t
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
  require_model_success: false
""",
        encoding="utf-8",
    )

    cfg = load_config(cfg_path)
    defs = load_eval_definitions(
        repo_root, cfg, artifact_type=ArtifactType.INSTRUCTIONS
    )

    assert len(defs) == 1
    assert defs[0].id == "instruction-eval"
    assert defs[0].artifact_type == ArtifactType.INSTRUCTIONS
