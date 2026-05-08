from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json

from pydantic_ai import Agent

from promptbench.config.schema import PromptBenchConfig
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
from promptbench.workflows.pydantic_models import (
    EnhanceModelOutput,
    SuggestionListOutput,
)


@dataclass
class EnhanceResult:
    suggestions: list[str]
    applied: bool
    revised_content: str | None = None


def _enhance_agent(model_name: str) -> Agent[None, EnhanceModelOutput]:
    return Agent(
        f"openai:{model_name}",
        output_type=EnhanceModelOutput,
        system_prompt=(
            "Provide concrete improvements for the artifact. Return suggestions and optional revised content."
        ),
    )


def _suggestion_agent(model_name: str) -> Agent[None, SuggestionListOutput]:
    return Agent(
        f"openai:{model_name}",
        output_type=SuggestionListOutput,
        system_prompt=(
            "Generate targeted suggestions only, tied to failing behavior. "
            "Return concise actionable bullet-like suggestions."
        ),
    )


def generate_enhancement_suggestions(
    content: str,
    *,
    config: PromptBenchConfig | None = None,
    repo: ReportRepository | None = None,
    run_id: int | None = None,
    model_override: str | None = None,
    fallback_models: list[str] | None = None,
    report_context: str | None = None,
) -> EnhanceResult:
    suggestions: list[str] = []
    revised_content: str | None = None

    if config is not None and repo is not None and run_id is not None:
        model_chain = resolve_workflow_model_chain(
            config,
            workflow="enhance",
            model_override=model_override,
            fallback_overrides=fallback_models,
        )
        if not model_chain:
            repo.add_model_invocation(
                run_id=run_id,
                workflow="enhance",
                provider_id="unconfigured",
                model="none",
                success=False,
                error_message="No providers.workflows.enhance model chain configured.",
                prompt_token_estimate=max(1, len(content) // 4),
            )
            event = repo.add_model_invocation_event(
                run_id=run_id,
                workflow="enhance",
                stage="enhance_suggest",
                provider_id="unconfigured",
                model="none",
                attempt_index=0,
                success=False,
                prompt_token_estimate=max(1, len(content) // 4),
                error_type="ConfigurationError",
                error_message="No providers.workflows.enhance model chain configured.",
            )
            repo.add_payload_log(
                run_id=run_id,
                invocation_event_id=event.id,
                workflow="enhance",
                stage="enhance_suggest",
                direction="prompt",
                payload_text=serialize_payload(
                    {"content": content, "report_context": report_context or ""}
                ),
            )
        # Stage 1: suggestion pre-pass
        for idx, provider in enumerate(model_chain):
            try:
                started = datetime.now(UTC)
                with provider_openai_env(provider):
                    payload = {
                        "content": content,
                        "report_context": report_context or "",
                    }
                    prompt_payload = serialize_payload(payload)
                    log_line(
                        config,
                        "trace",
                        f"enhance suggestion payload: {preview_payload(prompt_payload)}",
                    )
                    suggestion_output = _suggestion_agent(provider.model_name).run_sync(
                        json.dumps(payload, ensure_ascii=True)
                    )
                    suggestion_model_output = suggestion_output.output
                    response_payload = serialize_payload(
                        suggestion_model_output.model_dump()
                    )
                    raw_response_payload = extract_raw_response(suggestion_output)
                    log_line(
                        config,
                        "trace",
                        f"enhance suggestion response: {preview_payload(response_payload)}",
                    )
                finished = datetime.now(UTC)
                latency_ms = int((finished - started).total_seconds() * 1000)
                repo.add_model_invocation(
                    run_id=run_id,
                    workflow="enhance",
                    provider_id=provider.provider_id,
                    model=provider.model_name,
                    success=True,
                    fallback_used=idx > 0,
                    prompt_token_estimate=max(1, len(content) // 4),
                    latency_ms=latency_ms,
                )
                event = repo.add_model_invocation_event(
                    run_id=run_id,
                    workflow="enhance",
                    stage="enhance_suggest",
                    provider_id=provider.provider_id,
                    model=provider.model_name,
                    attempt_index=idx,
                    success=True,
                    fallback_used=idx > 0,
                    prompt_token_estimate=max(1, len(content) // 4),
                    latency_ms=latency_ms,
                    started_at=started,
                    finished_at=finished,
                )
                repo.add_payload_log(
                    run_id=run_id,
                    invocation_event_id=event.id,
                    workflow="enhance",
                    stage="enhance_suggest",
                    direction="prompt",
                    payload_text=prompt_payload,
                )
                repo.add_payload_log(
                    run_id=run_id,
                    invocation_event_id=event.id,
                    workflow="enhance",
                    stage="enhance_suggest",
                    direction="response",
                    payload_text=response_payload,
                )
                if raw_response_payload:
                    repo.add_payload_log(
                        run_id=run_id,
                        invocation_event_id=event.id,
                        workflow="enhance",
                        stage="enhance_suggest",
                        direction="response_raw",
                        payload_text=raw_response_payload,
                    )
                suggestions = suggestion_model_output.suggestions
                break
            except Exception as exc:  # noqa: BLE001
                error_details = extract_error_details(exc)
                error_text = str(error_details["error_message"])
                repo.add_model_invocation(
                    run_id=run_id,
                    workflow="enhance",
                    provider_id=provider.provider_id,
                    model=provider.model_name,
                    success=False,
                    fallback_used=idx > 0,
                    error_message=error_text,
                    prompt_token_estimate=max(1, len(content) // 4),
                )
                event = repo.add_model_invocation_event(
                    run_id=run_id,
                    workflow="enhance",
                    stage="enhance_suggest",
                    provider_id=provider.provider_id,
                    model=provider.model_name,
                    attempt_index=idx,
                    success=False,
                    fallback_used=idx > 0,
                    prompt_token_estimate=max(1, len(content) // 4),
                    error_type=str(error_details["error_type"]),
                    error_message=error_text,
                    provider_status_code=(
                        int(error_details["provider_status_code"])
                        if error_details["provider_status_code"] is not None
                        else None
                    ),
                )
                repo.add_payload_log(
                    run_id=run_id,
                    invocation_event_id=event.id,
                    workflow="enhance",
                    stage="enhance_suggest",
                    direction="prompt",
                    payload_text=serialize_payload(
                        {"content": content, "report_context": report_context or ""}
                    ),
                )
                repo.add_payload_log(
                    run_id=run_id,
                    invocation_event_id=event.id,
                    workflow="enhance",
                    stage="enhance_suggest",
                    direction="error",
                    payload_text=serialize_payload(error_details),
                )

        # Stage 2: rewrite/apply candidate generation
        for idx, provider in enumerate(model_chain):
            try:
                started = datetime.now(UTC)
                with provider_openai_env(provider):
                    payload = {
                        "content": content,
                        "suggestions": suggestions,
                        "report_context": report_context or "",
                    }
                    prompt_payload = serialize_payload(payload)
                    log_line(
                        config,
                        "trace",
                        f"enhance rewrite payload: {preview_payload(prompt_payload)}",
                    )
                    output = _enhance_agent(provider.model_name).run_sync(
                        json.dumps(payload, ensure_ascii=True)
                    )
                    enhance_model_output = output.output
                    response_payload = serialize_payload(
                        enhance_model_output.model_dump()
                    )
                    raw_response_payload = extract_raw_response(output)
                    log_line(
                        config,
                        "trace",
                        f"enhance rewrite response: {preview_payload(response_payload)}",
                    )
                finished = datetime.now(UTC)
                latency_ms = int((finished - started).total_seconds() * 1000)
                repo.add_model_invocation(
                    run_id=run_id,
                    workflow="enhance",
                    provider_id=provider.provider_id,
                    model=provider.model_name,
                    success=True,
                    fallback_used=idx > 0,
                    prompt_token_estimate=max(1, len(content) // 4),
                    latency_ms=latency_ms,
                )
                event = repo.add_model_invocation_event(
                    run_id=run_id,
                    workflow="enhance",
                    stage="enhance_rewrite",
                    provider_id=provider.provider_id,
                    model=provider.model_name,
                    attempt_index=idx,
                    success=True,
                    fallback_used=idx > 0,
                    prompt_token_estimate=max(1, len(content) // 4),
                    latency_ms=latency_ms,
                    started_at=started,
                    finished_at=finished,
                )
                repo.add_payload_log(
                    run_id=run_id,
                    invocation_event_id=event.id,
                    workflow="enhance",
                    stage="enhance_rewrite",
                    direction="prompt",
                    payload_text=prompt_payload,
                )
                repo.add_payload_log(
                    run_id=run_id,
                    invocation_event_id=event.id,
                    workflow="enhance",
                    stage="enhance_rewrite",
                    direction="response",
                    payload_text=response_payload,
                )
                if raw_response_payload:
                    repo.add_payload_log(
                        run_id=run_id,
                        invocation_event_id=event.id,
                        workflow="enhance",
                        stage="enhance_rewrite",
                        direction="response_raw",
                        payload_text=raw_response_payload,
                    )
                if not suggestions:
                    suggestions = enhance_model_output.suggestions
                revised_content = enhance_model_output.revised_content
                break
            except Exception as exc:  # noqa: BLE001
                error_details = extract_error_details(exc)
                error_text = str(error_details["error_message"])
                repo.add_model_invocation(
                    run_id=run_id,
                    workflow="enhance",
                    provider_id=provider.provider_id,
                    model=provider.model_name,
                    success=False,
                    fallback_used=idx > 0,
                    error_message=error_text,
                    prompt_token_estimate=max(1, len(content) // 4),
                )
                event = repo.add_model_invocation_event(
                    run_id=run_id,
                    workflow="enhance",
                    stage="enhance_rewrite",
                    provider_id=provider.provider_id,
                    model=provider.model_name,
                    attempt_index=idx,
                    success=False,
                    fallback_used=idx > 0,
                    prompt_token_estimate=max(1, len(content) // 4),
                    error_type=str(error_details["error_type"]),
                    error_message=error_text,
                    provider_status_code=(
                        int(error_details["provider_status_code"])
                        if error_details["provider_status_code"] is not None
                        else None
                    ),
                )
                repo.add_payload_log(
                    run_id=run_id,
                    invocation_event_id=event.id,
                    workflow="enhance",
                    stage="enhance_rewrite",
                    direction="prompt",
                    payload_text=serialize_payload(
                        {
                            "content": content,
                            "suggestions": suggestions,
                            "report_context": report_context or "",
                        }
                    ),
                )
                repo.add_payload_log(
                    run_id=run_id,
                    invocation_event_id=event.id,
                    workflow="enhance",
                    stage="enhance_rewrite",
                    direction="error",
                    payload_text=serialize_payload(error_details),
                )

    if not suggestions and revised_content is None:
        if not content.strip():
            suggestions.append("Add meaningful content.")
        if len(content.splitlines()) < 5:
            suggestions.append("Add more explicit examples and constraints.")
        if not suggestions:
            suggestions.append("Tighten wording and add concrete acceptance criteria.")
    return EnhanceResult(
        suggestions=suggestions, applied=False, revised_content=revised_content
    )
