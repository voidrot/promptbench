from pathlib import Path

from promptbench.config.loader import load_config
from promptbench.config.schema import ArtifactType
from promptbench.provider.runtime import resolve_workflow_model_chain
from promptbench.reporting.database import init_database, session_for
from promptbench.reporting.repository import ReportRepository
from promptbench.workflows.eval import run_eval


def test_eval_size_cap_gating(tmp_path: Path) -> None:
    repo_root = tmp_path
    (repo_root / "skills").mkdir(parents=True, exist_ok=True)
    skill_path = repo_root / "skills" / "my-skill.md"
    skill_path.write_text("line\n" * 50, encoding="utf-8")

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
  defaults:
    max_line_count: 10
    max_token_count: 10000
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
  registry:
    openai:
      kind: openai-compatible
      base_url: https://api.openai.com/v1
      api_key_env: OPENAI_API_KEY
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
  require_model_success: false
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
            enhance=True,
            loop=3,
        )

    assert outcomes
    assert outcomes[0].stop_reason == "size_cap_exceeded"


def test_eval_runs_all_tests_and_averages_score(tmp_path: Path) -> None:
    repo_root = tmp_path
    (repo_root / "skills").mkdir(parents=True, exist_ok=True)
    skill_path = repo_root / "skills" / "multi-skill.md"
    skill_path.write_text("alpha beta gamma\n", encoding="utf-8")

    eval_dir = repo_root / ".promptbench" / "evals"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "multi.eval.yaml").write_text(
        """
id: multi-eval
artifact_type: skills
target: multi-skill.md
tests:
  - id: t1
    prompt: alpha
  - id: t2
    prompt: zulu
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
  require_model_success: false
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
            target="multi-skill.md",
            enhance=False,
            loop=1,
        )

    assert outcomes
    assert outcomes[0].score < 0.8


def test_eval_definition_can_disable_provider_fallbacks(tmp_path: Path) -> None:
    repo_root = tmp_path
    (repo_root / "skills").mkdir(parents=True, exist_ok=True)
    (repo_root / "skills" / "main.md").write_text("hello\n", encoding="utf-8")

    eval_dir = repo_root / ".promptbench" / "evals"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "main.eval.yaml").write_text(
        """
id: fallback-disable-eval
artifact_type: skills
target: main.md
model: openai/primary-model
fallback_models: []
prompt: hello
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
  registry:
    openai:
      kind: openai-compatible
      base_url: http://localhost:1234/v1
      api_key_env: OPENAI_API_KEY
  workflows:
    eval:
      model: openai/workflow-primary
      fallback_models:
        - openai/workflow-fallback
      randomize_model: false
    judge:
      model: openai/workflow-primary
      fallback_models:
        - openai/workflow-fallback
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

    cfg = load_config(cfg_path)
    chain = resolve_workflow_model_chain(
        cfg,
        workflow="eval",
        model_override="openai/primary-model",
        fallback_overrides=[],
    )
    assert [row.model_name for row in chain] == ["primary-model"]
