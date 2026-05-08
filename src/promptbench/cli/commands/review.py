from __future__ import annotations

from pathlib import Path

import typer

from promptbench.config.loader import load_config
from promptbench.config.schema import ArtifactType
from promptbench.reporting.database import init_database, session_for
from promptbench.reporting.repository import ReportRepository
from promptbench.runtime_logging import log_line
from promptbench.workflows.review import run_review


def review_command(
    artifact_type: ArtifactType,
    target: str,
    require_model_success: bool | None = None,
    randomize_model: bool | None = None,
    model_random_seed: int | None = None,
    log_verbosity: str | None = None,
    config: Path = Path("promptbench.yaml"),
    repo: Path = Path("."),
) -> None:
    cfg = load_config(config)
    if require_model_success is not None:
        cfg.policies.require_model_success = require_model_success
    if randomize_model is not None:
        for workflow_name in ("review", "judge"):
            workflow_cfg = cfg.providers.workflows.get(workflow_name)
            if workflow_cfg is not None:
                workflow_cfg.randomize_model = randomize_model
    if model_random_seed is not None:
        cfg.policies.model_random_seed = model_random_seed
    if log_verbosity is not None:
        cfg.policies.log_verbosity = log_verbosity
    project_root = (repo / cfg.project.root).resolve()
    db_path = (project_root / cfg.output.database_path).resolve()
    engine = init_database(db_path)

    with session_for(engine) as session:
        repository = ReportRepository(session)
        result = run_review(project_root, cfg, repository, artifact_type, target)
        failed_model_calls = repository.count_failed_model_invocations(result.run_id)
        recent_errors = repository.recent_model_errors(result.run_id, limit=2)
        failure_types = repository.model_failure_breakdown_by_type(run_id=result.run_id)
        failure_statuses = repository.model_failure_breakdown_by_status(
            run_id=result.run_id
        )

    status = "PASSED" if not result.findings else "FAILED"
    typer.echo(
        f"[{status}] review {artifact_type.value}/{target} (run {result.run_id})"
    )
    log_line(cfg, "debug", f"review run completed run_id={result.run_id}")
    if failed_model_calls > 0:
        typer.echo(
            f"  warning: {failed_model_calls} model call(s) failed; review may include fallback behavior"
        )
        if failure_types:
            typer.echo("  failure types:")
            for row in failure_types:
                typer.echo(f"  - {row['error_type']}: {row['count']}")
        if failure_statuses:
            typer.echo("  provider status codes:")
            for row in failure_statuses:
                typer.echo(f"  - {row['provider_status_code']}: {row['count']}")
        for err in recent_errors:
            typer.echo(f"  - recent model error: {err}")
    if result.findings:
        typer.echo("  findings:")
        for finding in result.findings:
            typer.echo(f"  - {finding}")
    else:
        typer.echo("  no findings")
