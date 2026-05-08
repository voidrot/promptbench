from pathlib import Path

from promptbench.cli.commands.report import report_command
from promptbench.reporting.database import init_database, session_for
from promptbench.reporting.repository import ReportRepository
import json


def test_report_command_markdown_output(tmp_path: Path, capsys) -> None:
    cfg_path = tmp_path / "promptbench.yaml"
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

    db_path = tmp_path / ".promptbench" / "promptbench.db"
    engine = init_database(db_path)
    with session_for(engine) as session:
        repo = ReportRepository(session)
        run = repo.create_run("review")
        repo.add_model_invocation(
            run_id=run.id or 0,
            workflow="review",
            provider_id="llmstudio",
            model="nvidia/nemotron-3-nano-4b",
            success=False,
            error_message="connection refused",
        )
        artifact = repo.upsert_artifact("skills", "sample", "skills/sample.md")
        repo.add_enhancement_suggestion(
            run_id=run.id or 0,
            artifact_id=artifact.id or 0,
            suggestion=json.dumps(
                {"requested": 2, "effective": 1, "source": "provider-remote-cap"}
            ),
            applied=False,
            revision_summary="runtime_concurrency",
        )
        repo.finish_run(run)

    report_command(format="markdown", config=cfg_path, repo=tmp_path)
    out = capsys.readouterr().out
    assert "# PromptBench Report" in out
    assert "total_runs" in out
    assert "model_invocation_failures" in out
    assert "fallback_only_runs" in out
    assert "model_invocation_failed" in out
    assert "model_invocation_events" in out
    assert "payload_logs" in out
    assert "run_context_rows" in out
    assert "Concurrency" in out
    assert "Warnings" in out
