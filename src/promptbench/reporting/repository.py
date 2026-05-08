from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json

from sqlmodel import Session, desc, func, select

from promptbench.reporting.models import (
    Artifact,
    ArtifactMeasurement,
    AssertionResult,
    EnhancementSuggestion,
    EvalCase,
    LoopProgress,
    MetricResult,
    ModelInvocation,
    ModelInvocationEvent,
    PayloadLog,
    ReviewFinding,
    Run,
    RunContext,
    RunArtifact,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ReportRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_artifact(self, artifact_type: str, name: str, path: str) -> Artifact:
        stmt = select(Artifact).where(
            Artifact.artifact_type == artifact_type, Artifact.path == path
        )
        artifact = self.session.exec(stmt).first()
        if artifact is None:
            artifact = Artifact(artifact_type=artifact_type, name=name, path=path)
            self.session.add(artifact)
            self.session.commit()
            self.session.refresh(artifact)
            return artifact
        artifact.name = name
        artifact.updated_at = _utcnow()
        self.session.add(artifact)
        self.session.commit()
        self.session.refresh(artifact)
        return artifact

    def create_run(
        self,
        run_kind: str,
        status: str = "running",
        trigger: str = "manual",
        parent_run_id: int | None = None,
    ) -> Run:
        run = Run(
            run_kind=run_kind,
            status=status,
            trigger=trigger,
            parent_run_id=parent_run_id,
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def finish_run(
        self, run: Run, status: str = "completed", error_message: str | None = None
    ) -> Run:
        now = _utcnow()
        run.status = status
        run.finished_at = now
        run.error_message = error_message
        if run.started_at:
            started = run.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            delta = now - started
            run.duration_ms = int(delta.total_seconds() * 1000)
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def add_finding(
        self,
        run_id: int,
        severity: str,
        message: str,
        code: str | None = None,
        suggestion: str | None = None,
        location: str | None = None,
    ) -> ReviewFinding:
        finding = ReviewFinding(
            run_id=run_id,
            severity=severity,
            message=message,
            code=code,
            suggestion=suggestion,
            location=location,
        )
        self.session.add(finding)
        self.session.commit()
        self.session.refresh(finding)
        return finding

    def link_run_artifact(self, run_id: int, artifact_id: int) -> RunArtifact:
        row = RunArtifact(run_id=run_id, artifact_id=artifact_id)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def add_model_invocation(
        self,
        run_id: int,
        workflow: str,
        provider_id: str,
        model: str,
        success: bool = True,
        fallback_used: bool = False,
        prompt_token_estimate: int | None = None,
        completion_token_estimate: int | None = None,
        latency_ms: int | None = None,
        error_message: str | None = None,
    ) -> ModelInvocation:
        row = ModelInvocation(
            run_id=run_id,
            workflow=workflow,
            provider_id=provider_id,
            model=model,
            success=success,
            fallback_used=fallback_used,
            prompt_token_estimate=prompt_token_estimate,
            completion_token_estimate=completion_token_estimate,
            latency_ms=latency_ms,
            error_message=error_message,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def add_model_invocation_event(
        self,
        run_id: int,
        workflow: str,
        stage: str,
        provider_id: str,
        model: str,
        attempt_index: int,
        success: bool,
        fallback_used: bool = False,
        prompt_token_estimate: int | None = None,
        completion_token_estimate: int | None = None,
        latency_ms: int | None = None,
        cost_estimate_usd: float | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
        provider_status_code: int | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> ModelInvocationEvent:
        row = ModelInvocationEvent(
            run_id=run_id,
            workflow=workflow,
            stage=stage,
            provider_id=provider_id,
            model=model,
            attempt_index=attempt_index,
            success=success,
            fallback_used=fallback_used,
            prompt_token_estimate=prompt_token_estimate,
            completion_token_estimate=completion_token_estimate,
            latency_ms=latency_ms,
            cost_estimate_usd=cost_estimate_usd,
            error_type=error_type,
            error_message=error_message,
            provider_status_code=provider_status_code,
            started_at=started_at or _utcnow(),
            finished_at=finished_at,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def add_payload_log(
        self,
        run_id: int,
        workflow: str,
        stage: str,
        direction: str,
        payload_text: str,
        invocation_event_id: int | None = None,
        truncated: bool = False,
    ) -> PayloadLog:
        payload_hash = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
        row = PayloadLog(
            run_id=run_id,
            invocation_event_id=invocation_event_id,
            workflow=workflow,
            stage=stage,
            direction=direction,
            payload_text=payload_text,
            payload_hash=payload_hash,
            truncated=truncated,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def add_run_context(
        self,
        run_id: int,
        workflow: str,
        config_hash: str,
        require_model_success: bool,
        log_verbosity: str,
        artifact_type: str | None = None,
        target: str | None = None,
        requested_concurrency: int | None = None,
        effective_concurrency: int | None = None,
        concurrency_source: str | None = None,
    ) -> RunContext:
        row = RunContext(
            run_id=run_id,
            workflow=workflow,
            artifact_type=artifact_type,
            target=target,
            config_hash=config_hash,
            require_model_success=require_model_success,
            log_verbosity=log_verbosity,
            requested_concurrency=requested_concurrency,
            effective_concurrency=effective_concurrency,
            concurrency_source=concurrency_source,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def add_eval_case(
        self,
        run_id: int,
        eval_id: str,
        selected_prompt_text: str,
        pass_threshold: float,
        score: float,
        passed: bool,
        test_id: str | None = None,
        selected_prompt_id: str | None = None,
    ) -> EvalCase:
        row = EvalCase(
            run_id=run_id,
            eval_id=eval_id,
            test_id=test_id,
            selected_prompt_id=selected_prompt_id,
            selected_prompt_text=selected_prompt_text,
            pass_threshold=pass_threshold,
            score=score,
            passed=passed,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def add_assertion_result(
        self,
        eval_case_id: int,
        assertion_type: str,
        expected_value: str,
        passed: bool,
        actual_value: str | None = None,
        message: str | None = None,
    ) -> AssertionResult:
        row = AssertionResult(
            eval_case_id=eval_case_id,
            assertion_type=assertion_type,
            expected_value=expected_value,
            actual_value=actual_value,
            passed=passed,
            message=message,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def add_metric_result(
        self,
        eval_case_id: int,
        metric_name: str,
        metric_value: float,
        weight: float | None = None,
        weighted_value: float | None = None,
    ) -> MetricResult:
        row = MetricResult(
            eval_case_id=eval_case_id,
            metric_name=metric_name,
            metric_value=metric_value,
            weight=weight,
            weighted_value=weighted_value,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def add_measurement(
        self,
        run_id: int,
        artifact_id: int,
        line_count: int,
        token_count_estimate: int,
        max_line_count: int | None,
        max_token_count: int | None,
        within_limits: bool,
    ) -> ArtifactMeasurement:
        row = ArtifactMeasurement(
            run_id=run_id,
            artifact_id=artifact_id,
            line_count=line_count,
            token_count_estimate=token_count_estimate,
            max_line_count=max_line_count,
            max_token_count=max_token_count,
            within_limits=within_limits,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def add_loop_progress(
        self,
        root_run_id: int,
        iteration: int,
        score: float,
        threshold: float,
        passed: bool,
        stop_reason: str,
    ) -> LoopProgress:
        row = LoopProgress(
            root_run_id=root_run_id,
            iteration=iteration,
            score=score,
            threshold=threshold,
            passed=passed,
            stop_reason=stop_reason,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def add_enhancement_suggestion(
        self,
        run_id: int,
        artifact_id: int,
        suggestion: str,
        applied: bool = False,
        revision_summary: str | None = None,
    ) -> EnhancementSuggestion:
        row = EnhancementSuggestion(
            run_id=run_id,
            artifact_id=artifact_id,
            suggestion=suggestion,
            applied=applied,
            revision_summary=revision_summary,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def recent_runs(self, limit: int = 50) -> list[Run]:
        stmt = select(Run).order_by(desc(Run.started_at)).limit(limit)
        return list(self.session.exec(stmt).all())

    def count_failed_model_invocations(self, run_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(ModelInvocation)
            .where(ModelInvocation.run_id == run_id, ModelInvocation.success.is_(False))
        )
        return int(self.session.exec(stmt).one())

    def recent_model_errors(self, run_id: int, limit: int = 3) -> list[str]:
        stmt = (
            select(ModelInvocation)
            .where(ModelInvocation.run_id == run_id, ModelInvocation.success.is_(False))
            .order_by(desc(ModelInvocation.id))
            .limit(limit)
        )
        rows = list(self.session.exec(stmt).all())
        return [row.error_message for row in rows if row.error_message]

    def recent_runtime_concurrency(self, run_id: int) -> dict[str, object] | None:
        stmt = (
            select(EnhancementSuggestion)
            .where(
                EnhancementSuggestion.run_id == run_id,
                EnhancementSuggestion.revision_summary == "runtime_concurrency",
            )
            .order_by(desc(EnhancementSuggestion.id))
            .limit(1)
        )
        row = self.session.exec(stmt).first()
        if row is None:
            return None
        try:
            parsed = json.loads(row.suggestion)
            if isinstance(parsed, dict):
                return parsed
        except Exception:  # noqa: BLE001
            return None
        return None

    def count_payload_logs(self, run_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(PayloadLog)
            .where(PayloadLog.run_id == run_id)
        )
        return int(self.session.exec(stmt).one())

    def count_model_invocation_events(self, run_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(ModelInvocationEvent)
            .where(ModelInvocationEvent.run_id == run_id)
        )
        return int(self.session.exec(stmt).one())

    def total_payload_logs(self) -> int:
        stmt = select(func.count()).select_from(PayloadLog)
        return int(self.session.exec(stmt).one())

    def total_model_invocation_events(self) -> int:
        stmt = select(func.count()).select_from(ModelInvocationEvent)
        return int(self.session.exec(stmt).one())

    def total_run_context_rows(self) -> int:
        stmt = select(func.count()).select_from(RunContext)
        return int(self.session.exec(stmt).one())

    def run_context_for_run(self, run_id: int) -> RunContext | None:
        stmt = select(RunContext).where(RunContext.run_id == run_id).limit(1)
        return self.session.exec(stmt).first()

    def model_failure_breakdown_by_type(
        self, run_id: int | None = None
    ) -> list[dict[str, object]]:
        stmt = (
            select(
                ModelInvocationEvent.error_type,
                func.count().label("count"),
            )
            .where(ModelInvocationEvent.success.is_(False))
            .group_by(ModelInvocationEvent.error_type)
            .order_by(desc("count"))
        )
        if run_id is not None:
            stmt = stmt.where(ModelInvocationEvent.run_id == run_id)
        rows = self.session.exec(stmt).all()
        return [
            {
                "error_type": error_type or "unknown",
                "count": int(count),
            }
            for error_type, count in rows
        ]

    def model_failure_breakdown_by_status(
        self, run_id: int | None = None
    ) -> list[dict[str, object]]:
        stmt = (
            select(
                ModelInvocationEvent.provider_status_code,
                func.count().label("count"),
            )
            .where(ModelInvocationEvent.success.is_(False))
            .group_by(ModelInvocationEvent.provider_status_code)
            .order_by(desc("count"))
        )
        if run_id is not None:
            stmt = stmt.where(ModelInvocationEvent.run_id == run_id)
        rows = self.session.exec(stmt).all()
        return [
            {
                "provider_status_code": status_code,
                "count": int(count),
            }
            for status_code, count in rows
        ]

    def model_failure_breakdown_by_stage(
        self, run_id: int | None = None
    ) -> list[dict[str, object]]:
        stmt = (
            select(
                ModelInvocationEvent.workflow,
                ModelInvocationEvent.stage,
                func.count().label("count"),
            )
            .where(ModelInvocationEvent.success.is_(False))
            .group_by(ModelInvocationEvent.workflow, ModelInvocationEvent.stage)
            .order_by(desc("count"))
        )
        if run_id is not None:
            stmt = stmt.where(ModelInvocationEvent.run_id == run_id)
        rows = self.session.exec(stmt).all()
        return [
            {
                "workflow": workflow,
                "stage": stage,
                "count": int(count),
            }
            for workflow, stage, count in rows
        ]

    def recent_failure_events(
        self, limit: int = 20, run_id: int | None = None
    ) -> list[ModelInvocationEvent]:
        stmt = select(ModelInvocationEvent).where(
            ModelInvocationEvent.success.is_(False)
        )
        if run_id is not None:
            stmt = stmt.where(ModelInvocationEvent.run_id == run_id)
        stmt = stmt.order_by(desc(ModelInvocationEvent.id)).limit(limit)
        return list(self.session.exec(stmt).all())
