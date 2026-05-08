from __future__ import annotations

import json
from datetime import UTC, datetime
from os import makedirs
from pathlib import Path

import typer

from promptbench.config.loader import load_config
from promptbench.config.schema import ArtifactType
from promptbench.reporting.database import init_database, session_for
from promptbench.reporting.repository import ReportRepository
from promptbench.runtime_logging import log_line
from promptbench.workflows.eval import run_eval


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def _friendly_stop_reason(stop_reason: str) -> str:
    mapping = {
        "threshold_met": "pass threshold reached",
        "max_iterations": "max iterations reached",
        "size_cap_exceeded": "file size limit exceeded",
        "model_invocation_failed": "model invocation failed",
        "best_iteration_restored": "best iteration retained",
    }
    return mapping.get(stop_reason, stop_reason.replace("_", " "))


def eval_command(
    artifact_type: ArtifactType | None = None,
    target: str | None = None,
    enhance: bool = False,
    loop: int | None = None,
    concurrency: int | None = None,
    continuous: bool = False,
    continuous_max_rounds: int = 6,
    require_model_success: bool = True,
    log_verbosity: str | None = None,
    output: Path | None = None,
    config: Path = Path("promptbench.yaml"),
    repo: Path = Path("."),
) -> None:
    cfg = load_config(config)
    cfg.policies.require_model_success = require_model_success
    if log_verbosity is not None:
        cfg.policies.log_verbosity = log_verbosity
    project_root = (repo / cfg.project.root).resolve()
    db_path = (project_root / cfg.output.database_path).resolve()
    engine = init_database(db_path)

    with session_for(engine) as session:
        repository = ReportRepository(session)
        outcomes = run_eval(
            base_dir=project_root,
            config=cfg,
            repo=repository,
            artifact_type=artifact_type,
            target=target,
            enhance=enhance,
            loop=loop,
            concurrency=concurrency,
            continuous=continuous,
            continuous_max_rounds=continuous_max_rounds,
        )
        failed_model_calls = {}
        model_errors = {}
        failure_types_by_run: dict[int, list[dict[str, object]]] = {}
        failure_status_by_run: dict[int, list[dict[str, object]]] = {}
        for outcome in outcomes:
            failed = repository.count_failed_model_invocations(outcome.run_id)
            failed_model_calls[outcome.run_id] = failed
            if failed > 0:
                model_errors[outcome.run_id] = repository.recent_model_errors(
                    outcome.run_id, limit=2
                )
                failure_types_by_run[outcome.run_id] = (
                    repository.model_failure_breakdown_by_type(run_id=outcome.run_id)
                )
                failure_status_by_run[outcome.run_id] = (
                    repository.model_failure_breakdown_by_status(run_id=outcome.run_id)
                )

    if output is None:
        reports_dir = (project_root / cfg.output.reports_dir).resolve()
        makedirs(reports_dir, exist_ok=True)
        suffix = artifact_type.value if artifact_type is not None else "all"
        output = reports_dir / f"eval-{suffix}-{_utc_stamp()}.json"

    payload = {
        "artifact_type": artifact_type.value if artifact_type else None,
        "target": target,
        "enhance": enhance,
        "loop": loop,
        "concurrency": concurrency,
        "continuous": continuous,
        "continuous_max_rounds": continuous_max_rounds,
        "outcomes": [o.__dict__ for o in outcomes],
    }
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    log_line(cfg, "debug", f"wrote eval trajectory output: {output}")

    if not outcomes:
        typer.echo("No eval definitions found.")
        return

    for outcome in outcomes:
        pct = round(outcome.score * 100, 1)
        status = "PASSED" if outcome.passed else "FAILED"
        typer.echo(
            f"[{status}] {outcome.eval_id} (run {outcome.run_id}) - score {pct}%"
        )
        typer.echo(
            f"  stop: {_friendly_stop_reason(outcome.stop_reason)} | "
            f"iterations: {outcome.iterations} | "
            f"best iteration: {outcome.best_iteration}"
        )
        typer.echo(
            f"  improvement rounds: {outcome.continuous_rounds} | "
            f"content changed: {'yes' if outcome.changed else 'no'}"
        )
        typer.echo(
            f"  concurrency: requested {outcome.concurrency_requested}, "
            f"used {outcome.concurrency_effective} ({outcome.concurrency_source})"
        )
        failed = failed_model_calls.get(outcome.run_id, 0)
        if failed > 0:
            typer.echo(
                f"  warning: {failed} model call(s) failed; score may include fallback behavior"
            )
            if failure_types_by_run.get(outcome.run_id):
                typer.echo("  failure types:")
                for row in failure_types_by_run[outcome.run_id]:
                    typer.echo(f"  - {row['error_type']}: {row['count']}")
            if failure_status_by_run.get(outcome.run_id):
                typer.echo("  provider status codes:")
                for row in failure_status_by_run[outcome.run_id]:
                    typer.echo(f"  - {row['provider_status_code']}: {row['count']}")
            for err in model_errors.get(outcome.run_id, []):
                typer.echo(f"  - recent model error: {err}")
        typer.echo("")
    typer.echo(f"output={output}")
