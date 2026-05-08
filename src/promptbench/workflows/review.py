from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from pathlib import Path
from typing import cast

from pydantic_ai import Agent

from promptbench.artifacts.resolver import resolve_artifact
from promptbench.config.schema import ArtifactType, PromptBenchConfig
from promptbench.provider.runtime import (
    provider_openai_env,
    resolve_workflow_model_chain,
)
from promptbench.reporting.repository import ReportRepository
from promptbench.runtime_logging import (
    extract_error_details,
    extract_raw_response,
    log_line,
    preview_payload,
    serialize_payload,
)
from promptbench.validators.skills_spec import validate_skill_file
from promptbench.workflows.pydantic_models import ReviewModelOutput


@dataclass
class ReviewResult:
    run_id: int
    findings: list[str]
    model_success: bool


def _review_agent(model_name: str) -> Agent[None, ReviewModelOutput]:
    return cast(
        Agent[None, ReviewModelOutput],
        Agent(
            f"openai:{model_name}",
            output_type=ReviewModelOutput,
            system_prompt=(
                "Review the artifact content and return concise, structured findings with severity, "
                "message, and optional suggestion/location."
            ),
        ),
    )


def run_review(
    base_dir: Path,
    config: PromptBenchConfig,
    repo: ReportRepository,
    artifact_type: ArtifactType,
    target: str,
) -> ReviewResult:
    run = repo.create_run("review")

    config_hash = hashlib.sha256(config.model_dump_json().encode("utf-8")).hexdigest()
    repo.add_run_context(
        run_id=run.id or 0,
        workflow="review",
        artifact_type=artifact_type.value,
        target=target,
        config_hash=config_hash,
        require_model_success=config.policies.require_model_success,
        log_verbosity=config.policies.log_verbosity,
    )

    artifact = resolve_artifact(base_dir, config, artifact_type, target)
    stored_artifact = repo.upsert_artifact(
        artifact_type.value, artifact.name, str(artifact.path)
    )

    findings: list[str] = []
    if artifact_type == ArtifactType.SKILLS:
        findings = validate_skill_file(artifact.path)
        for finding in findings:
            repo.add_finding(run.id or 0, severity="error", message=finding)

    model_chain = resolve_workflow_model_chain(config, workflow="review")
    if not model_chain:
        model_chain = resolve_workflow_model_chain(config, workflow="judge")
    model_output: ReviewModelOutput | None = None
    model_success = False
    for idx, provider in enumerate(model_chain):
        try:
            started = datetime.now(UTC)
            with provider_openai_env(provider):
                prompt_payload = serialize_payload(artifact.content)
                log_line(
                    config,
                    "trace",
                    f"review prompt payload: {preview_payload(prompt_payload)}",
                )
                review_result = _review_agent(provider.model_name).run_sync(
                    artifact.content
                )
                model_output = review_result.output
                response_payload = serialize_payload(model_output.model_dump())
                raw_response_payload = extract_raw_response(review_result)
                log_line(
                    config,
                    "trace",
                    f"review model response: {preview_payload(response_payload)}",
                )
            finished = datetime.now(UTC)
            latency_ms = int((finished - started).total_seconds() * 1000)
            repo.add_model_invocation(
                run_id=run.id or 0,
                workflow="review",
                provider_id=provider.provider_id,
                model=provider.model_name,
                success=True,
                fallback_used=idx > 0,
                prompt_token_estimate=artifact.token_count_estimate,
                latency_ms=latency_ms,
            )
            event = repo.add_model_invocation_event(
                run_id=run.id or 0,
                workflow="review",
                stage="review",
                provider_id=provider.provider_id,
                model=provider.model_name,
                attempt_index=idx,
                success=True,
                fallback_used=idx > 0,
                prompt_token_estimate=artifact.token_count_estimate,
                latency_ms=latency_ms,
                started_at=started,
                finished_at=finished,
            )
            repo.add_payload_log(
                run_id=run.id or 0,
                invocation_event_id=event.id,
                workflow="review",
                stage="review",
                direction="prompt",
                payload_text=prompt_payload,
            )
            repo.add_payload_log(
                run_id=run.id or 0,
                invocation_event_id=event.id,
                workflow="review",
                stage="review",
                direction="response",
                payload_text=response_payload,
            )
            if raw_response_payload:
                repo.add_payload_log(
                    run_id=run.id or 0,
                    invocation_event_id=event.id,
                    workflow="review",
                    stage="review",
                    direction="response_raw",
                    payload_text=raw_response_payload,
                )
            model_success = True
            break
        except Exception as exc:  # noqa: BLE001
            finished = datetime.now(UTC)
            error_details = extract_error_details(exc)
            error_text = str(error_details["error_message"])
            repo.add_model_invocation(
                run_id=run.id or 0,
                workflow="review",
                provider_id=provider.provider_id,
                model=provider.model_name,
                success=False,
                fallback_used=idx > 0,
                error_message=error_text,
                prompt_token_estimate=artifact.token_count_estimate,
            )
            event = repo.add_model_invocation_event(
                run_id=run.id or 0,
                workflow="review",
                stage="review",
                provider_id=provider.provider_id,
                model=provider.model_name,
                attempt_index=idx,
                success=False,
                fallback_used=idx > 0,
                prompt_token_estimate=artifact.token_count_estimate,
                error_type=str(error_details["error_type"]),
                error_message=error_text,
                provider_status_code=(
                    int(error_details["provider_status_code"])
                    if error_details["provider_status_code"] is not None
                    else None
                ),
                finished_at=finished,
            )
            repo.add_payload_log(
                run_id=run.id or 0,
                invocation_event_id=event.id,
                workflow="review",
                stage="review",
                direction="prompt",
                payload_text=serialize_payload(artifact.content),
            )
            repo.add_payload_log(
                run_id=run.id or 0,
                invocation_event_id=event.id,
                workflow="review",
                stage="review",
                direction="error",
                payload_text=serialize_payload(error_details),
            )

    if not model_chain:
        repo.add_model_invocation(
            run_id=run.id or 0,
            workflow="review",
            provider_id="unconfigured",
            model="none",
            success=False,
            error_message="No providers.workflows.review/judge model chain configured.",
            prompt_token_estimate=artifact.token_count_estimate,
        )
        event = repo.add_model_invocation_event(
            run_id=run.id or 0,
            workflow="review",
            stage="review",
            provider_id="unconfigured",
            model="none",
            attempt_index=0,
            success=False,
            prompt_token_estimate=artifact.token_count_estimate,
            error_type="ConfigurationError",
            error_message="No providers.workflows.review/judge model chain configured.",
        )
        repo.add_payload_log(
            run_id=run.id or 0,
            invocation_event_id=event.id,
            workflow="review",
            stage="review",
            direction="prompt",
            payload_text=serialize_payload(artifact.content),
        )

    if model_output is not None:
        for item in model_output.findings:
            repo.add_finding(
                run.id or 0,
                severity=item.severity,
                message=item.message,
                code=item.code,
                suggestion=item.suggestion,
                location=item.location,
            )
            findings.append(item.message)

    if config.policies.require_model_success and not model_success:
        findings.append("Model invocation failed and require_model_success=true.")

    repo.add_measurement(
        run_id=run.id or 0,
        artifact_id=stored_artifact.id or 0,
        line_count=artifact.line_count,
        token_count_estimate=artifact.token_count_estimate,
        max_line_count=None,
        max_token_count=None,
        within_limits=True,
    )

    status = "completed" if not findings else "failed"
    repo.finish_run(run, status=status)
    return ReviewResult(
        run_id=run.id or 0,
        findings=findings,
        model_success=model_success,
    )
