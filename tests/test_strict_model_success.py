from pathlib import Path

from promptbench.config.loader import load_config
from promptbench.config.schema import ArtifactType
from promptbench.reporting.database import init_database, session_for
from promptbench.reporting.repository import ReportRepository
from promptbench.workflows.eval import run_eval


def test_eval_requires_model_success_by_default(tmp_path: Path) -> None:
    repo_root = tmp_path
    (repo_root / "skills").mkdir(parents=True, exist_ok=True)
    (repo_root / "skills" / "my-skill.md").write_text("hello\n", encoding="utf-8")

    eval_dir = repo_root / ".promptbench" / "evals"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "my.eval.yaml").write_text(
        """
id: my-eval
artifact_type: skills
target: my-skill.md
prompt: evaluate this
""",
        encoding="utf-8",
    )

    cfg_path = repo_root / "promptbench.yaml"
    cfg_path.write_text(
        """
version: 1
project:
  name: test
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
  reports_dir: .promptbench/reports
policies:
  fail_on_severity: error
  fail_on_score_below: 0.7
  max_workers: 1
  require_model_success: true
""",
        encoding="utf-8",
    )

    cfg = load_config(cfg_path)
    engine = init_database(repo_root / ".promptbench" / "promptbench.db")
    with session_for(engine) as session:
        repository = ReportRepository(session)
        outcomes = run_eval(
            base_dir=repo_root,
            config=cfg,
            repo=repository,
            artifact_type=ArtifactType.SKILLS,
            target="my-skill.md",
            enhance=False,
            loop=1,
        )

    assert outcomes
    assert outcomes[0].stop_reason == "model_invocation_failed"
