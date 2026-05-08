from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer
from sqlmodel import Session, func, select

from promptbench.config.loader import load_config
from promptbench.reporting.database import init_database, session_for
from promptbench.reporting.repository import ReportRepository
from promptbench.reporting.models import Artifact, LoopProgress, Run


def report_command(
    since: str | None = None,
    format: str = "json",
    config: Path = Path("promptbench.yaml"),
    repo: Path = Path("."),
) -> None:
    cfg = load_config(config)
    project_root = (repo / cfg.project.root).resolve()
    db_path = (project_root / cfg.output.database_path).resolve()
    engine = init_database(db_path)

    with session_for(engine) as session:
        repository = ReportRepository(session)
        rows = repository.recent_runs(limit=200)

    since_dt: datetime | None = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            raise typer.BadParameter("--since must be ISO date or datetime") from None

    if since_dt is not None:
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=UTC)
        filtered_rows = []
        for row in rows:
            started = row.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            if started >= since_dt:
                filtered_rows.append(row)
        rows = filtered_rows

    model_failures_total = 0
    fallback_only_runs = 0
    concurrency_rollups: dict[tuple[int, int, str], int] = {}
    run_warnings: list[dict[str, object]] = []
    with session_for(engine) as session:
        repository = ReportRepository(session)
        for row in rows:
            failed = repository.count_failed_model_invocations(row.id or 0)
            model_failures_total += failed
            runtime_concurrency = repository.recent_runtime_concurrency(row.id or 0)
            if runtime_concurrency is not None:
                req = int(runtime_concurrency.get("requested", 0) or 0)
                eff = int(runtime_concurrency.get("effective", 0) or 0)
                src = str(runtime_concurrency.get("source", "unknown"))
                key = (req, eff, src)
                concurrency_rollups[key] = concurrency_rollups.get(key, 0) + 1
            if row.run_kind in {"review", "eval", "enhance"} and failed > 0:
                fallback_only_runs += 1
                run_warnings.append(
                    {
                        "run_id": row.id,
                        "run_kind": row.run_kind,
                        "failed_model_calls": failed,
                        "errors": repository.recent_model_errors(row.id or 0, limit=2),
                    }
                )

    with Session(engine) as session:
        total_runs = session.exec(select(func.count()).select_from(Run)).one()
        completed_runs = session.exec(
            select(func.count()).select_from(Run).where(Run.status == "completed")
        ).one()
        total_artifacts = session.exec(select(func.count()).select_from(Artifact)).one()
        cap_exceeded = session.exec(
            select(func.count())
            .select_from(LoopProgress)
            .where(LoopProgress.stop_reason == "size_cap_exceeded")
        ).one()
        model_failed_stops = session.exec(
            select(func.count())
            .select_from(LoopProgress)
            .where(LoopProgress.stop_reason == "model_invocation_failed")
        ).one()
        best_restore_stops = session.exec(
            select(func.count())
            .select_from(LoopProgress)
            .where(LoopProgress.stop_reason == "best_iteration_restored")
        ).one()

    with session_for(engine) as session:
        repository = ReportRepository(session)
        payload_logs_total = repository.total_payload_logs()
        model_events_total = repository.total_model_invocation_events()
        run_context_rows = repository.total_run_context_rows()
        failure_by_type = repository.model_failure_breakdown_by_type()
        failure_by_status = repository.model_failure_breakdown_by_status()
        failure_by_stage = repository.model_failure_breakdown_by_stage()
        recent_failure_events = repository.recent_failure_events(limit=10)

    summary = {
        "since": since,
        "total_runs": int(total_runs),
        "completed_runs": int(completed_runs),
        "total_artifacts": int(total_artifacts),
        "size_cap_exceeded": int(cap_exceeded),
        "model_invocation_failed": int(model_failed_stops),
        "best_iteration_restored": int(best_restore_stops),
        "model_invocation_failures": int(model_failures_total),
        "fallback_only_runs": int(fallback_only_runs),
        "model_invocation_events": int(model_events_total),
        "payload_logs": int(payload_logs_total),
        "run_context_rows": int(run_context_rows),
        "model_failure_breakdown_by_type": failure_by_type,
        "model_failure_breakdown_by_status": failure_by_status,
        "model_failure_breakdown_by_stage": failure_by_stage,
        "recent_failure_events": [
            {
                "id": row.id,
                "run_id": row.run_id,
                "workflow": row.workflow,
                "stage": row.stage,
                "provider_id": row.provider_id,
                "model": row.model,
                "attempt_index": row.attempt_index,
                "fallback_used": row.fallback_used,
                "error_type": row.error_type,
                "provider_status_code": row.provider_status_code,
                "error_message": row.error_message,
                "started_at": str(row.started_at),
                "finished_at": str(row.finished_at),
            }
            for row in recent_failure_events
        ],
        "concurrency_rollups": [
            {
                "requested": req,
                "effective": eff,
                "source": src,
                "count": count,
            }
            for (req, eff, src), count in sorted(
                concurrency_rollups.items(), key=lambda item: item[1], reverse=True
            )
        ],
        "run_warnings": run_warnings,
        "recent_runs": [
            {
                "id": row.id,
                "kind": row.run_kind,
                "status": row.status,
                "started_at": str(row.started_at),
            }
            for row in rows
        ],
    }

    if format == "markdown":
        typer.echo("# PromptBench Report")
        typer.echo(f"- total_runs: {summary['total_runs']}")
        typer.echo(f"- completed_runs: {summary['completed_runs']}")
        typer.echo(f"- total_artifacts: {summary['total_artifacts']}")
        typer.echo(f"- size_cap_exceeded: {summary['size_cap_exceeded']}")
        typer.echo(f"- model_invocation_failed: {summary['model_invocation_failed']}")
        typer.echo(f"- best_iteration_restored: {summary['best_iteration_restored']}")
        typer.echo(
            f"- model_invocation_failures: {summary['model_invocation_failures']}"
        )
        typer.echo(f"- fallback_only_runs: {summary['fallback_only_runs']}")
        typer.echo(f"- model_invocation_events: {summary['model_invocation_events']}")
        typer.echo(f"- payload_logs: {summary['payload_logs']}")
        typer.echo(f"- run_context_rows: {summary['run_context_rows']}")
        if summary["model_failure_breakdown_by_type"]:
            typer.echo("\n## Failure Types")
            for row in summary["model_failure_breakdown_by_type"]:
                typer.echo(f"- {row['error_type']}: {row['count']}")
        if summary["model_failure_breakdown_by_status"]:
            typer.echo("\n## Failure Status Codes")
            for row in summary["model_failure_breakdown_by_status"]:
                label = row["provider_status_code"]
                typer.echo(f"- {label}: {row['count']}")
        if summary["model_failure_breakdown_by_stage"]:
            typer.echo("\n## Failure Stages")
            for row in summary["model_failure_breakdown_by_stage"]:
                typer.echo(f"- {row['workflow']}/{row['stage']}: {row['count']}")
        if summary["concurrency_rollups"]:
            typer.echo("\n## Concurrency")
            for row in summary["concurrency_rollups"]:
                typer.echo(
                    f"- requested={row['requested']} effective={row['effective']} source={row['source']} count={row['count']}"
                )
        if summary["run_warnings"]:
            typer.echo("\n## Warnings")
            for warning in summary["run_warnings"]:
                typer.echo(
                    f"- run_id={warning['run_id']} kind={warning['run_kind']} "
                    f"failed_model_calls={warning['failed_model_calls']}"
                )
                for err in warning["errors"]:
                    typer.echo(f"  - error: {err}")
        typer.echo("\n## Recent Runs")
        for row in summary["recent_runs"]:
            typer.echo(
                f"- id={row['id']} kind={row['kind']} status={row['status']} started_at={row['started_at']}"
            )
    else:
        typer.echo(summary)
