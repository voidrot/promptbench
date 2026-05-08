from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Artifact(SQLModel, table=True):
    __tablename__ = "artifacts"

    id: int | None = Field(default=None, primary_key=True)
    artifact_type: str
    name: str
    path: str
    content_hash: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Run(SQLModel, table=True):
    __tablename__ = "runs"

    id: int | None = Field(default=None, primary_key=True)
    run_kind: str
    status: str
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: datetime | None = None
    duration_ms: int | None = None
    trigger: str = "manual"
    parent_run_id: int | None = Field(default=None, foreign_key="runs.id")
    error_message: str | None = None


class RunArtifact(SQLModel, table=True):
    __tablename__ = "run_artifacts"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id")
    artifact_id: int = Field(foreign_key="artifacts.id")


class ModelInvocation(SQLModel, table=True):
    __tablename__ = "model_invocations"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id")
    workflow: str
    provider_id: str
    model: str
    fallback_used: bool = False
    prompt_token_estimate: int | None = None
    completion_token_estimate: int | None = None
    latency_ms: int | None = None
    success: bool = True
    error_message: str | None = None


class EvalCase(SQLModel, table=True):
    __tablename__ = "eval_cases"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id")
    eval_id: str
    test_id: str | None = None
    selected_prompt_id: str | None = None
    selected_prompt_text: str = ""
    pass_threshold: float = 0.0
    score: float = 0.0
    passed: bool = False


class AssertionResult(SQLModel, table=True):
    __tablename__ = "assertion_results"

    id: int | None = Field(default=None, primary_key=True)
    eval_case_id: int = Field(foreign_key="eval_cases.id")
    assertion_type: str
    expected_value: str
    actual_value: str | None = None
    passed: bool = False
    message: str | None = None


class MetricResult(SQLModel, table=True):
    __tablename__ = "metric_results"

    id: int | None = Field(default=None, primary_key=True)
    eval_case_id: int = Field(foreign_key="eval_cases.id")
    metric_name: str
    metric_value: float
    weight: float | None = None
    weighted_value: float | None = None


class ReviewFinding(SQLModel, table=True):
    __tablename__ = "review_findings"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id")
    severity: str
    code: str | None = None
    message: str
    suggestion: str | None = None
    location: str | None = None


class EnhancementSuggestion(SQLModel, table=True):
    __tablename__ = "enhancement_suggestions"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id")
    artifact_id: int = Field(foreign_key="artifacts.id")
    suggestion: str
    applied: bool = False
    revision_summary: str | None = None


class LoopProgress(SQLModel, table=True):
    __tablename__ = "loop_progress"

    id: int | None = Field(default=None, primary_key=True)
    root_run_id: int = Field(foreign_key="runs.id")
    iteration: int
    score: float
    threshold: float
    passed: bool
    stop_reason: str


class ArtifactMeasurement(SQLModel, table=True):
    __tablename__ = "artifact_measurements"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id")
    artifact_id: int = Field(foreign_key="artifacts.id")
    line_count: int
    token_count_estimate: int
    max_line_count: int | None = None
    max_token_count: int | None = None
    within_limits: bool = True


class ModelInvocationEvent(SQLModel, table=True):
    __tablename__ = "model_invocation_events"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id")
    workflow: str
    stage: str
    provider_id: str
    model: str
    attempt_index: int = 0
    fallback_used: bool = False
    success: bool = True
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: datetime | None = None
    latency_ms: int | None = None
    prompt_token_estimate: int | None = None
    completion_token_estimate: int | None = None
    cost_estimate_usd: float | None = None
    error_type: str | None = None
    error_message: str | None = None
    provider_status_code: int | None = None


class PayloadLog(SQLModel, table=True):
    __tablename__ = "payload_logs"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id")
    invocation_event_id: int | None = Field(
        default=None, foreign_key="model_invocation_events.id"
    )
    workflow: str
    stage: str
    direction: str
    payload_text: str
    payload_hash: str
    truncated: bool = False
    created_at: datetime = Field(default_factory=_utcnow)


class RunContext(SQLModel, table=True):
    __tablename__ = "run_context"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id")
    workflow: str
    artifact_type: str | None = None
    target: str | None = None
    config_hash: str
    require_model_success: bool = True
    log_verbosity: str = "normal"
    requested_concurrency: int | None = None
    effective_concurrency: int | None = None
    concurrency_source: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
