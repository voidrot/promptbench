from pathlib import Path

from promptbench.reporting.database import init_database, session_for
from promptbench.reporting.repository import ReportRepository


def test_repository_basic_flow(tmp_path: Path) -> None:
    engine = init_database(tmp_path / "test.db")
    with session_for(engine) as session:
        repo = ReportRepository(session)
        run = repo.create_run("review")
        artifact = repo.upsert_artifact("skills", "my-skill", "skills/my-skill.md")
        repo.add_measurement(
            run_id=run.id or 0,
            artifact_id=artifact.id or 0,
            line_count=10,
            token_count_estimate=30,
            max_line_count=100,
            max_token_count=200,
            within_limits=True,
        )
        repo.finish_run(run)

        runs = repo.recent_runs()
        assert runs
        assert runs[0].run_kind == "review"


def test_repository_telemetry_tables(tmp_path: Path) -> None:
    engine = init_database(tmp_path / "telemetry.db")
    with session_for(engine) as session:
        repo = ReportRepository(session)
        run = repo.create_run("eval")
        artifact = repo.upsert_artifact("skills", "sample", "skills/sample.md")
        repo.link_run_artifact(run.id or 0, artifact.id or 0)
        repo.add_run_context(
            run_id=run.id or 0,
            workflow="eval",
            artifact_type="skills",
            target="sample.md",
            config_hash="abc123",
            require_model_success=True,
            log_verbosity="trace",
            requested_concurrency=2,
            effective_concurrency=1,
            concurrency_source="provider",
        )
        event = repo.add_model_invocation_event(
            run_id=run.id or 0,
            workflow="eval",
            stage="eval",
            provider_id="local",
            model="m1",
            attempt_index=0,
            success=True,
            latency_ms=42,
        )
        repo.add_payload_log(
            run_id=run.id or 0,
            invocation_event_id=event.id,
            workflow="eval",
            stage="eval",
            direction="prompt",
            payload_text="PROMPT",
        )
        repo.add_payload_log(
            run_id=run.id or 0,
            invocation_event_id=event.id,
            workflow="eval",
            stage="eval",
            direction="response_raw",
            payload_text='{"raw": true}',
        )

        assert repo.total_model_invocation_events() == 1
        assert repo.total_payload_logs() == 2
        assert repo.total_run_context_rows() == 1
        assert repo.count_model_invocation_events(run.id or 0) == 1
        assert repo.count_payload_logs(run.id or 0) == 2
        assert repo.run_context_for_run(run.id or 0) is not None
