from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from flask import Flask, abort, jsonify, render_template, request
from sqlmodel import Session, select

from promptbench.config.schema import PromptBenchConfig
from promptbench.provider.runtime import resolve_workflow_model_chain
from promptbench.reporting.database import init_database
from promptbench.reporting.models import (
    Artifact,
    ArtifactMeasurement,
    EvalCase,
    LoopProgress,
    MetricResult,
    ModelInvocationEvent,
    PayloadLog,
    ReviewFinding,
    Run,
    RunContext,
)


def create_app(db_path: Path, config: PromptBenchConfig | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    engine = init_database(db_path)

    def _q(name: str, default: str = "") -> str:
        return (request.args.get(name) or default).strip()

    def _parse_int(name: str, default: int) -> int:
        try:
            value = int(request.args.get(name, default))
        except Exception:  # noqa: BLE001
            return default
        return max(1, value)

    def _base_runs_stmt(status: str, kind: str):
        stmt = select(Run)
        if status:
            stmt = stmt.where(Run.status == status)
        if kind:
            stmt = stmt.where(Run.run_kind == kind)
        return stmt

    def _parse_dt(name: str) -> datetime | None:
        raw = _q(name)
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed

    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    def _within_range(
        value: datetime | None, since_dt: datetime | None, until_dt: datetime | None
    ) -> bool:
        if value is None:
            return False
        point = _as_utc(value)
        if point is None:
            return False
        if since_dt is not None and point < since_dt:
            return False
        if until_dt is not None and point > until_dt:
            return False
        return True

    def _sort_rows(
        rows: list[object], sort_key: str, sort_dir: str, key_fn_map: dict[str, object]
    ) -> list[object]:
        reverse = sort_dir == "desc"
        key_fn = key_fn_map.get(sort_key)
        if key_fn is None:
            return rows
        return sorted(rows, key=key_fn, reverse=reverse)

    @app.get("/")
    def dashboard():
        with Session(engine) as session:
            recent_runs = list(
                session.exec(select(Run).order_by(Run.id.desc()).limit(12)).all()
            )
            total_runs = len(session.exec(select(Run)).all())
            completed_runs = len(
                session.exec(select(Run).where(Run.status == "completed")).all()
            )
            failed_runs = len(
                session.exec(select(Run).where(Run.status == "failed")).all()
            )
            payload_logs_count = len(session.exec(select(PayloadLog)).all())
            model_events_count = len(session.exec(select(ModelInvocationEvent)).all())
            pass_rate = (completed_runs / total_runs) if total_runs else 0.0

            recent_scores = list(
                session.exec(
                    select(EvalCase).order_by(EvalCase.id.desc()).limit(20)
                ).all()
            )
            chart_labels = [f"run {case.run_id}" for case in reversed(recent_scores)]
            chart_scores = [
                round(case.score * 100, 1) for case in reversed(recent_scores)
            ]

            stop_rows = list(
                session.exec(
                    select(LoopProgress).order_by(LoopProgress.id.desc()).limit(200)
                ).all()
            )
            stop_reason_counts: dict[str, int] = {}
            for row in stop_rows:
                stop_reason_counts[row.stop_reason] = (
                    stop_reason_counts.get(row.stop_reason, 0) + 1
                )

            failing_runs = [r for r in recent_runs if r.status == "failed"][:8]

        return render_template(
            "dashboard.html",
            recent_runs=recent_runs,
            total_runs=total_runs,
            completed_runs=completed_runs,
            failed_runs=failed_runs,
            pass_rate=pass_rate,
            payload_logs_count=payload_logs_count,
            model_events_count=model_events_count,
            chart_labels=chart_labels,
            chart_scores=chart_scores,
            stop_reason_counts=stop_reason_counts,
            failing_runs=failing_runs,
        )

    @app.get("/runs")
    def runs():
        status = _q("status")
        kind = _q("kind")
        since = _q("since")
        until = _q("until")
        since_dt = _parse_dt("since")
        until_dt = _parse_dt("until")
        sort = _q("sort", "id")
        sort_dir = _q("dir", "desc")
        if sort_dir not in {"asc", "desc"}:
            sort_dir = "desc"
        page = _parse_int("page", 1)
        page_size = min(_parse_int("page_size", 25), 100)
        offset = (page - 1) * page_size

        with Session(engine) as session:
            stmt = _base_runs_stmt(status, kind)
            all_rows = list(session.exec(stmt.order_by(Run.id.desc())).all())
            all_rows = [
                row
                for row in all_rows
                if _within_range(row.started_at, since_dt, until_dt)
            ]
            all_rows = _sort_rows(
                all_rows,
                sort,
                sort_dir,
                {
                    "id": lambda r: r.id or 0,
                    "kind": lambda r: r.run_kind,
                    "status": lambda r: r.status,
                    "trigger": lambda r: r.trigger,
                    "started_at": lambda r: (
                        _as_utc(r.started_at) or datetime.min.replace(tzinfo=UTC)
                    ),
                    "finished_at": lambda r: (
                        _as_utc(r.finished_at) or datetime.min.replace(tzinfo=UTC)
                    ),
                },
            )
            total = len(all_rows)
            rows = all_rows[offset : offset + page_size]

        return render_template(
            "runs.html",
            runs=rows,
            total=total,
            page=page,
            page_size=page_size,
            status=status,
            kind=kind,
            since=since,
            until=until,
            sort=sort,
            sort_dir=sort_dir,
        )

    @app.get("/runs/<int:run_id>")
    def run_detail(run_id: int):
        with Session(engine) as session:
            run = session.get(Run, run_id)
            if run is None:
                abort(404)
            findings = list(
                session.exec(
                    select(ReviewFinding).where(ReviewFinding.run_id == run_id)
                ).all()
            )
            eval_cases = list(
                session.exec(select(EvalCase).where(EvalCase.run_id == run_id)).all()
            )
            loop_rows = list(
                session.exec(
                    select(LoopProgress).where(LoopProgress.root_run_id == run_id)
                ).all()
            )
            case_ids = [case.id for case in eval_cases if case.id is not None]
            metrics = []
            if case_ids:
                metrics = list(
                    session.exec(
                        select(MetricResult).where(
                            MetricResult.eval_case_id.in_(case_ids)
                        )
                    ).all()
                )
            model_events = list(
                session.exec(
                    select(ModelInvocationEvent)
                    .where(ModelInvocationEvent.run_id == run_id)
                    .order_by(ModelInvocationEvent.id.desc())
                ).all()
            )
            payload_logs = list(
                session.exec(
                    select(PayloadLog)
                    .where(PayloadLog.run_id == run_id)
                    .order_by(PayloadLog.id.desc())
                    .limit(200)
                ).all()
            )
            failure_events = [row for row in model_events if not row.success]
            failure_by_type_counts: dict[str, int] = {}
            failure_by_status_counts: dict[str, int] = {}
            failure_by_stage_counts: dict[str, int] = {}
            for row in failure_events:
                type_key = row.error_type or "unknown"
                failure_by_type_counts[type_key] = (
                    failure_by_type_counts.get(type_key, 0) + 1
                )

                status_key = (
                    str(row.provider_status_code)
                    if row.provider_status_code is not None
                    else "none"
                )
                failure_by_status_counts[status_key] = (
                    failure_by_status_counts.get(status_key, 0) + 1
                )

                stage_key = f"{row.workflow}/{row.stage}"
                failure_by_stage_counts[stage_key] = (
                    failure_by_stage_counts.get(stage_key, 0) + 1
                )

            failure_by_type = [
                {"error_type": key, "count": count}
                for key, count in sorted(
                    failure_by_type_counts.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            ]
            failure_by_status = [
                {"provider_status_code": key, "count": count}
                for key, count in sorted(
                    failure_by_status_counts.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            ]
            failure_by_stage = [
                {"stage": key, "count": count}
                for key, count in sorted(
                    failure_by_stage_counts.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            ]

            error_payload_by_event: dict[int, int] = {}
            for row in payload_logs:
                if row.direction != "error" or row.invocation_event_id is None:
                    continue
                if row.invocation_event_id not in error_payload_by_event:
                    error_payload_by_event[row.invocation_event_id] = row.id or 0

            recent_failure_events = []
            for event in failure_events[:10]:
                recent_failure_events.append(
                    {
                        "id": event.id,
                        "workflow": event.workflow,
                        "stage": event.stage,
                        "provider_id": event.provider_id,
                        "model": event.model,
                        "attempt_index": event.attempt_index,
                        "error_type": event.error_type,
                        "provider_status_code": event.provider_status_code,
                        "error_message": event.error_message,
                        "payload_log_id": error_payload_by_event.get(event.id or 0),
                    }
                )

            payload_groups: dict[int, dict[str, object]] = {}
            for row in reversed(payload_logs):
                key = row.invocation_event_id or (10_000_000 + (row.id or 0))
                if key not in payload_groups:
                    payload_groups[key] = {
                        "invocation_event_id": row.invocation_event_id,
                        "workflow": row.workflow,
                        "stage": row.stage,
                        "prompt": None,
                        "response": None,
                        "response_raw": None,
                        "error": None,
                    }
                if row.direction == "prompt":
                    payload_groups[key]["prompt"] = row
                elif row.direction == "response":
                    payload_groups[key]["response"] = row
                elif row.direction == "response_raw":
                    payload_groups[key]["response_raw"] = row
                elif row.direction == "error":
                    payload_groups[key]["error"] = row
            payload_groups_ordered = list(reversed(list(payload_groups.values())))
            run_context = session.exec(
                select(RunContext).where(RunContext.run_id == run_id).limit(1)
            ).first()

            metric_chart_labels = [m.metric_name for m in metrics[:30]]
            metric_chart_values = [
                round(float(m.metric_value), 4) for m in metrics[:30]
            ]

        return render_template(
            "run_detail.html",
            run=run,
            findings=findings,
            eval_cases=eval_cases,
            loop_rows=loop_rows,
            metrics=metrics,
            model_events=model_events,
            payload_logs=payload_logs,
            payload_groups=payload_groups_ordered,
            run_context=run_context,
            failure_by_type=failure_by_type,
            failure_by_status=failure_by_status,
            failure_by_stage=failure_by_stage,
            recent_failure_events=recent_failure_events,
            metric_chart_labels=metric_chart_labels,
            metric_chart_values=metric_chart_values,
        )

    @app.get("/artifacts")
    def artifacts():
        artifact_type = _q("type")
        since = _q("since")
        until = _q("until")
        since_dt = _parse_dt("since")
        until_dt = _parse_dt("until")
        sort = _q("sort", "updated_at")
        sort_dir = _q("dir", "desc")
        if sort_dir not in {"asc", "desc"}:
            sort_dir = "desc"
        with Session(engine) as session:
            stmt = select(Artifact)
            if artifact_type:
                stmt = stmt.where(Artifact.artifact_type == artifact_type)
            rows = list(session.exec(stmt.order_by(Artifact.updated_at.desc())).all())
            rows = [
                row for row in rows if _within_range(row.updated_at, since_dt, until_dt)
            ]
            rows = _sort_rows(
                rows,
                sort,
                sort_dir,
                {
                    "id": lambda r: r.id or 0,
                    "type": lambda r: r.artifact_type,
                    "name": lambda r: r.name,
                    "path": lambda r: r.path,
                    "updated_at": lambda r: (
                        _as_utc(r.updated_at) or datetime.min.replace(tzinfo=UTC)
                    ),
                },
            )
        return render_template(
            "artifacts.html",
            artifacts=rows,
            artifact_type=artifact_type,
            since=since,
            until=until,
            sort=sort,
            sort_dir=sort_dir,
        )

    @app.get("/artifacts/<int:artifact_id>")
    def artifact_detail(artifact_id: int):
        with Session(engine) as session:
            artifact = session.get(Artifact, artifact_id)
            if artifact is None:
                abort(404)
            measurements = list(
                session.exec(
                    select(ArtifactMeasurement)
                    .where(ArtifactMeasurement.artifact_id == artifact_id)
                    .order_by(ArtifactMeasurement.id.desc())
                    .limit(200)
                ).all()
            )
            linked_runs = [m.run_id for m in measurements if m.run_id is not None]
            runs = []
            if linked_runs:
                runs = list(
                    session.exec(
                        select(Run)
                        .where(Run.id.in_(linked_runs))
                        .order_by(Run.id.desc())
                    ).all()
                )

            measurement_labels = [str(m.run_id) for m in reversed(measurements[:60])]
            measurement_tokens = [
                m.token_count_estimate for m in reversed(measurements[:60])
            ]

        return render_template(
            "artifact_detail.html",
            artifact=artifact,
            measurements=measurements,
            runs=runs,
            measurement_labels=measurement_labels,
            measurement_tokens=measurement_tokens,
        )

    @app.get("/metrics")
    def metrics():
        name = _q("name")
        since = _q("since")
        until = _q("until")
        since_dt = _parse_dt("since")
        until_dt = _parse_dt("until")
        sort = _q("sort", "id")
        sort_dir = _q("dir", "desc")
        if sort_dir not in {"asc", "desc"}:
            sort_dir = "desc"
        page = _parse_int("page", 1)
        page_size = min(_parse_int("page_size", 50), 200)
        offset = (page - 1) * page_size

        with Session(engine) as session:
            stmt = select(MetricResult)
            if name:
                stmt = stmt.where(MetricResult.metric_name == name)
            all_rows = list(session.exec(stmt.order_by(MetricResult.id.desc())).all())

            case_ids = [
                row.eval_case_id for row in all_rows if row.eval_case_id is not None
            ]
            case_run_map: dict[int, tuple[int, datetime | None]] = {}
            if case_ids:
                eval_cases = list(
                    session.exec(
                        select(EvalCase).where(EvalCase.id.in_(case_ids))
                    ).all()
                )
                run_ids = [
                    case.run_id for case in eval_cases if case.run_id is not None
                ]
                run_time_map: dict[int, datetime | None] = {}
                if run_ids:
                    runs = list(
                        session.exec(select(Run).where(Run.id.in_(run_ids))).all()
                    )
                    run_time_map = {run.id or 0: run.started_at for run in runs}
                case_run_map = {
                    case.id or 0: (case.run_id, run_time_map.get(case.run_id))
                    for case in eval_cases
                }

            if since_dt is not None or until_dt is not None:
                filtered: list[MetricResult] = []
                for row in all_rows:
                    _, run_started = case_run_map.get(row.eval_case_id, (0, None))
                    if _within_range(run_started, since_dt, until_dt):
                        filtered.append(row)
                all_rows = filtered

            all_rows = _sort_rows(
                all_rows,
                sort,
                sort_dir,
                {
                    "id": lambda r: r.id or 0,
                    "eval_case_id": lambda r: r.eval_case_id,
                    "name": lambda r: r.metric_name,
                    "value": lambda r: r.metric_value,
                    "weight": lambda r: r.weight if r.weight is not None else -1.0,
                },
            )
            total = len(all_rows)
            rows = all_rows[offset : offset + page_size]

            labels = [str(m.eval_case_id) for m in reversed(rows[:60])]
            values = [round(float(m.metric_value), 4) for m in reversed(rows[:60])]

        return render_template(
            "metrics.html",
            metrics=rows,
            total=total,
            page=page,
            page_size=page_size,
            metric_name=name,
            since=since,
            until=until,
            sort=sort,
            sort_dir=sort_dir,
            chart_labels=labels,
            chart_values=values,
        )

    @app.get("/api/charts/score-trend")
    def api_score_trend():
        with Session(engine) as session:
            rows = list(
                session.exec(
                    select(EvalCase).order_by(EvalCase.id.desc()).limit(100)
                ).all()
            )
        labels = [f"run {r.run_id}" for r in reversed(rows)]
        values = [round(r.score * 100, 2) for r in reversed(rows)]
        return jsonify({"labels": labels, "values": values})

    @app.get("/api/healthcheck/models")
    def api_healthcheck_models():
        if config is None:
            return jsonify({"ok": False, "error": "serve config unavailable"}), 400

        checks: list[dict[str, object]] = []
        for workflow in ["review", "eval", "enhance"]:
            chain = resolve_workflow_model_chain(config, workflow=workflow)
            if not chain:
                checks.append(
                    {
                        "workflow": workflow,
                        "provider_id": "unconfigured",
                        "model": "none",
                        "ok": False,
                        "status_code": None,
                        "error": "No model chain configured",
                    }
                )
                continue

            for provider in chain:
                url = provider.base_url.rstrip("/") + "/models"
                try:
                    req = Request(url, method="GET")
                    with urlopen(req, timeout=5) as resp:  # noqa: S310
                        status_code = int(getattr(resp, "status", 200) or 200)
                    checks.append(
                        {
                            "workflow": workflow,
                            "provider_id": provider.provider_id,
                            "model": provider.model_name,
                            "ok": 200 <= status_code < 300,
                            "status_code": status_code,
                            "error": None,
                        }
                    )
                except URLError as exc:
                    checks.append(
                        {
                            "workflow": workflow,
                            "provider_id": provider.provider_id,
                            "model": provider.model_name,
                            "ok": False,
                            "status_code": None,
                            "error": str(exc.reason)
                            if hasattr(exc, "reason")
                            else str(exc),
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    checks.append(
                        {
                            "workflow": workflow,
                            "provider_id": provider.provider_id,
                            "model": provider.model_name,
                            "ok": False,
                            "status_code": None,
                            "error": str(exc),
                        }
                    )

        return jsonify(
            {
                "ok": all(bool(item["ok"]) for item in checks),
                "checks": checks,
            }
        )

    return app
