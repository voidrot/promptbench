from __future__ import annotations

from dataclasses import asdict
import json
from datetime import UTC, datetime
from os import makedirs
from pathlib import Path

import typer
from sqlmodel import select

from promptbench.config.loader import load_config
from promptbench.config.schema import ArtifactType
from promptbench.reporting.database import init_database, session_for
from promptbench.reporting.models import Run
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


def eval_all_command(
    artifact_type: ArtifactType,
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
            target=None,
            enhance=enhance,
            loop=loop,
            concurrency=concurrency,
            continuous=continuous,
            continuous_max_rounds=continuous_max_rounds,
        )

        total = len(outcomes)
        passed = sum(1 for o in outcomes if o.passed)
        failed = total - passed
        failure_types_by_run: dict[int, list[dict[str, object]]] = {}
        failure_status_by_run: dict[int, list[dict[str, object]]] = {}
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
                f"  concurrency: requested {outcome.concurrency_requested}, "
                f"used {outcome.concurrency_effective} ({outcome.concurrency_source})"
            )
            failed_model_calls = repository.count_failed_model_invocations(
                outcome.run_id
            )
            if failed_model_calls > 0:
                failure_types_by_run[outcome.run_id] = (
                    repository.model_failure_breakdown_by_type(run_id=outcome.run_id)
                )
                failure_status_by_run[outcome.run_id] = (
                    repository.model_failure_breakdown_by_status(run_id=outcome.run_id)
                )
                typer.echo(
                    f"  warning: {failed_model_calls} model call(s) failed; score may include fallback behavior"
                )
                if failure_types_by_run.get(outcome.run_id):
                    typer.echo("  failure types:")
                    for row in failure_types_by_run[outcome.run_id]:
                        typer.echo(f"  - {row['error_type']}: {row['count']}")
                if failure_status_by_run.get(outcome.run_id):
                    typer.echo("  provider status codes:")
                    for row in failure_status_by_run[outcome.run_id]:
                        typer.echo(f"  - {row['provider_status_code']}: {row['count']}")
                for err in repository.recent_model_errors(outcome.run_id, limit=2):
                    typer.echo(f"  - recent model error: {err}")
            typer.echo("")

        run_rows = list(
            session.exec(
                select(Run)
                .where(Run.run_kind == "eval")
                .order_by(Run.id.desc())
                .limit(max(1, total))
            ).all()
        )

    if output is None:
        reports_dir = (project_root / cfg.output.reports_dir).resolve()
        makedirs(reports_dir, exist_ok=True)
        output = reports_dir / f"eval-all-{artifact_type.value}-{_utc_stamp()}.json"

    payload = {
        "artifact_type": artifact_type.value,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errored_runs": sum(1 for r in run_rows if r.status == "failed"),
        },
        "outcomes": [asdict(o) for o in outcomes],
    }
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    log_line(cfg, "debug", f"wrote eval-all trajectory output: {output}")

    typer.echo("summary:")
    typer.echo(f"- artifact_type={artifact_type.value}")
    typer.echo(f"- total={total}")
    typer.echo(f"- passed={passed}")
    typer.echo(f"- failed={failed}")
    typer.echo(f"- errored_runs={sum(1 for r in run_rows if r.status == 'failed')}")
    typer.echo(f"- output={output}")


__all__ = ["eval_all_command"]
