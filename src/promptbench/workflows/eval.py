from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from pydantic_ai import Agent

from promptbench.artifacts.resolver import resolve_artifact
from promptbench.config.schema import (
    ArtifactType,
    EvalDefinition,
    EvalTest,
    ObjectLimits,
    PromptBenchConfig,
)
from promptbench.evals.loader import load_eval_definitions
from promptbench.evals.selection import select_prompt
from promptbench.provider.runtime import (
    provider_openai_env,
    resolve_dynamic_concurrency,
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
from promptbench.workflows.common import resolve_effective_limits, within_limits
from promptbench.workflows.enhance import generate_enhancement_suggestions
from promptbench.workflows.pydantic_models import EvalModelOutput


CONTINUOUS_IMPROVE_MAX_ROUNDS = 6


@dataclass
class EvalOutcome:
    run_id: int
    eval_id: str
    score: float
    passed: bool
    stop_reason: str
    iterations: int = 1
    best_iteration: int = 1
    continuous_rounds: int = 1
    changed: bool = False
    concurrency_requested: int | None = None
    concurrency_effective: int = 1
    concurrency_source: str = "policies.max_workers"


@dataclass
class DefinitionRoundState:
    score: float
    passed: bool
    stop_reason: str
    iterations_run: int
    best_iteration: int
    strict_model_failure: bool
    changed: bool
    test_count: int


@dataclass
class TestEvalResult:
    test: EvalTest
    prompt_id: str | None
    prompt_text: str
    effective_limits: ObjectLimits
    allowed: bool
    eval_output: EvalModelOutput
    model_success: bool
    invocations: list[dict[str, object]]


def _eval_agent(model_name: str) -> Agent[None, EvalModelOutput]:
    return cast(
        Agent[None, EvalModelOutput],
        Agent(
            f"openai:{model_name}",
            output_type=EvalModelOutput,
            system_prompt=(
                "Evaluate the artifact against the given prompt and return a normalized score from 0 to 1, "
                "metric breakdown, and assertion pass/fail messages."
            ),
        ),
    )


def _as_int(value: object | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _as_datetime(value: object | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    return None


def _simple_score(artifact_content: str, prompt_text: str) -> float:
    if not prompt_text:
        return 0.0
    content = artifact_content.lower()
    tokens = [word for word in prompt_text.lower().split() if len(word) > 3]
    if not tokens:
        return 0.5
    hits = sum(1 for token in set(tokens) if token in content)
    return min(1.0, hits / max(5, len(set(tokens))))


def _run_eval_model_for_test(
    *,
    config: PromptBenchConfig,
    definition: EvalDefinition,
    test: EvalTest,
    artifact_content: str,
    prompt_text: str,
    prompt_token_estimate: int,
) -> tuple[EvalModelOutput, bool, list[dict[str, object]]]:
    model_override = test.model or definition.model
    test_randomize_model = (
        test.randomize_model
        if test.randomize_model is not None
        else definition.randomize_model
    )
    fallback_models = (
        test.fallback_models
        if test.fallback_models is not None
        else definition.fallback_models
    )

    model_chain = resolve_workflow_model_chain(
        config,
        workflow="judge",
        model_override=model_override,
        fallback_overrides=fallback_models,
        randomize_model=test_randomize_model,
        randomization_key=(
            f"{definition.id}:{test.id or 'default'}:{prompt_text[:80]}:{prompt_token_estimate}"
        ),
    )
    if not model_chain:
        model_chain = resolve_workflow_model_chain(
            config,
            workflow="eval",
            model_override=model_override,
            fallback_overrides=fallback_models,
            randomize_model=test_randomize_model,
            randomization_key=(
                f"{definition.id}:{test.id or 'default'}:{prompt_text[:80]}:{prompt_token_estimate}"
            ),
        )
    invocations: list[dict[str, object]] = []

    if not model_chain:
        prompt_payload = serialize_payload(
            {"prompt": prompt_text, "artifact": artifact_content}
        )
        invocations.append(
            {
                "stage": "eval",
                "provider_id": "unconfigured",
                "model": "none",
                "attempt_index": 0,
                "success": False,
                "fallback_used": False,
                "prompt_token_estimate": prompt_token_estimate,
                "latency_ms": None,
                "started_at": None,
                "finished_at": None,
                "error_type": "ConfigurationError",
                "error_message": "No providers.workflows.judge/eval model chain configured.",
                "provider_status_code": None,
                "prompt_payload": prompt_payload,
                "response_payload": None,
                "response_raw_payload": None,
                "error_payload": None,
            }
        )
        return (
            EvalModelOutput(
                score=_simple_score(artifact_content, prompt_text), metrics=[]
            ),
            False,
            invocations,
        )

    for idx, provider in enumerate(model_chain):
        try:
            started = datetime.now(UTC)
            prompt_payload = serialize_payload(
                {"prompt": prompt_text, "artifact": artifact_content}
            )
            with provider_openai_env(provider):
                log_line(
                    config,
                    "trace",
                    f"eval prompt payload: {preview_payload(prompt_payload)}",
                )
                eval_result = _eval_agent(provider.model_name).run_sync(
                    f"PROMPT:\n{prompt_text}\n\nARTIFACT:\n{artifact_content}"
                )
                output = eval_result.output
                raw_response_payload = extract_raw_response(eval_result)
            finished = datetime.now(UTC)
            latency_ms = int((finished - started).total_seconds() * 1000)
            response_payload = serialize_payload(output.model_dump())
            log_line(
                config,
                "trace",
                f"eval model response: {preview_payload(response_payload)}",
            )
            invocations.append(
                {
                    "stage": "eval",
                    "provider_id": provider.provider_id,
                    "model": provider.model_name,
                    "attempt_index": idx,
                    "success": True,
                    "fallback_used": idx > 0,
                    "prompt_token_estimate": prompt_token_estimate,
                    "latency_ms": latency_ms,
                    "started_at": started,
                    "finished_at": finished,
                    "error_message": None,
                    "error_type": None,
                    "prompt_payload": prompt_payload,
                    "response_payload": response_payload,
                    "response_raw_payload": raw_response_payload,
                }
            )
            output.score = max(0.0, min(1.0, output.score))
            return output, True, invocations
        except Exception as exc:  # noqa: BLE001
            finished = datetime.now(UTC)
            error_details = extract_error_details(exc)
            error_text = str(error_details["error_message"])
            invocations.append(
                {
                    "stage": "eval",
                    "provider_id": provider.provider_id,
                    "model": provider.model_name,
                    "attempt_index": idx,
                    "success": False,
                    "fallback_used": idx > 0,
                    "prompt_token_estimate": prompt_token_estimate,
                    "latency_ms": None,
                    "started_at": None,
                    "finished_at": finished,
                    "error_message": error_text,
                    "error_type": str(error_details["error_type"]),
                    "provider_status_code": error_details["provider_status_code"],
                    "prompt_payload": serialize_payload(
                        {"prompt": prompt_text, "artifact": artifact_content}
                    ),
                    "response_payload": None,
                    "response_raw_payload": None,
                    "error_payload": serialize_payload(error_details),
                }
            )

    return (
        EvalModelOutput(score=_simple_score(artifact_content, prompt_text), metrics=[]),
        False,
        invocations,
    )


def _evaluate_single_test(
    config: PromptBenchConfig,
    definition: EvalDefinition,
    test: EvalTest,
    artifact_content: str,
    artifact_line_count: int,
    artifact_token_estimate: int,
) -> TestEvalResult:
    prompt_id, prompt_text = select_prompt(test)
    effective_limits = resolve_effective_limits(
        config,
        definition.artifact_type,
        test.object_limits or definition.object_limits,
    )
    allowed = within_limits(
        artifact_line_count,
        artifact_token_estimate,
        effective_limits,
    )
    eval_output, model_success, invocations = _run_eval_model_for_test(
        config=config,
        definition=definition,
        test=test,
        artifact_content=artifact_content,
        prompt_text=prompt_text,
        prompt_token_estimate=artifact_token_estimate,
    )
    return TestEvalResult(
        test=test,
        prompt_id=prompt_id,
        prompt_text=prompt_text,
        effective_limits=effective_limits,
        allowed=allowed,
        eval_output=eval_output,
        model_success=model_success,
        invocations=invocations,
    )


def _record_assertions(
    repo: ReportRepository, eval_case_id: int, output: EvalModelOutput
) -> None:
    for message in output.assertions_passed:
        repo.add_assertion_result(
            eval_case_id=eval_case_id,
            assertion_type="generic",
            expected_value=message,
            actual_value=message,
            passed=True,
            message=message,
        )
    for message in output.assertions_failed:
        repo.add_assertion_result(
            eval_case_id=eval_case_id,
            assertion_type="generic",
            expected_value=message,
            actual_value=None,
            passed=False,
            message=message,
        )


def _record_metrics(
    repo: ReportRepository, eval_case_id: int, output: EvalModelOutput
) -> None:
    for item in output.metrics:
        weighted = item.metric_value * item.weight if item.weight is not None else None
        repo.add_metric_result(
            eval_case_id=eval_case_id,
            metric_name=item.metric_name,
            metric_value=item.metric_value,
            weight=item.weight,
            weighted_value=weighted,
        )


def _iter_eval_tests(defn: EvalDefinition) -> list[EvalTest]:
    if defn.tests:
        return list(defn.tests)
    return [
        EvalTest(
            id=None,
            prompt=defn.prompt,
            prompts=defn.prompts,
            model=defn.model,
            fallback_models=defn.fallback_models,
            inputs=defn.inputs,
            expected=defn.expected,
            references=defn.references,
            object_limits=defn.object_limits,
        )
    ]


def _write_revised_content(path: Path, revised_content: str) -> bool:
    old = path.read_text(encoding="utf-8")
    if old == revised_content:
        return False
    path.write_text(revised_content, encoding="utf-8")
    return True


def _run_definition_round(
    *,
    base_dir: Path,
    config: PromptBenchConfig,
    repo: ReportRepository,
    definition: EvalDefinition,
    root_run_id: int,
    loop_limit: int,
    concurrency_effective: int,
    enhance: bool,
    seen_suggestions: set[str],
) -> DefinitionRoundState:
    best_score = -1.0
    best_iteration = 1
    best_passed = False
    best_stop_reason = "max_iterations"
    strict_model_success_failed = False
    changed = False
    iterations_run = 0
    test_count = 0

    for iteration in range(1, loop_limit + 1):
        iterations_run = iteration
        artifact = resolve_artifact(
            base_dir, config, definition.artifact_type, definition.target
        )
        stored_artifact = repo.upsert_artifact(
            definition.artifact_type.value, artifact.name, str(artifact.path)
        )
        repo.link_run_artifact(root_run_id, stored_artifact.id or 0)

        tests = _iter_eval_tests(definition)
        test_count = len(tests)
        test_scores: list[float] = []
        model_success_all = True
        stop_reason = "max_iterations"
        allowed_all = True

        with ThreadPoolExecutor(max_workers=max(1, concurrency_effective)) as executor:
            futures = [
                executor.submit(
                    _evaluate_single_test,
                    config,
                    definition,
                    test,
                    artifact.content,
                    artifact.line_count,
                    artifact.token_count_estimate,
                )
                for test in tests
            ]

            for future in as_completed(futures):
                result = future.result()
                allowed_all = allowed_all and result.allowed
                repo.add_measurement(
                    run_id=root_run_id,
                    artifact_id=stored_artifact.id or 0,
                    line_count=artifact.line_count,
                    token_count_estimate=artifact.token_count_estimate,
                    max_line_count=result.effective_limits.max_line_count,
                    max_token_count=result.effective_limits.max_token_count,
                    within_limits=result.allowed,
                )

                model_success_all = model_success_all and result.model_success
                test_scores.append(result.eval_output.score)

                case_passed = (
                    result.eval_output.score >= config.workflows.eval.pass_threshold
                )
                eval_case = repo.add_eval_case(
                    run_id=root_run_id,
                    eval_id=definition.id,
                    test_id=result.test.id,
                    selected_prompt_id=result.prompt_id,
                    selected_prompt_text=result.prompt_text,
                    pass_threshold=config.workflows.eval.pass_threshold,
                    score=result.eval_output.score,
                    passed=case_passed,
                )
                _record_assertions(repo, eval_case.id or 0, result.eval_output)
                _record_metrics(repo, eval_case.id or 0, result.eval_output)

                for invocation in result.invocations:
                    repo.add_model_invocation(
                        run_id=root_run_id,
                        workflow="eval",
                        provider_id=str(invocation["provider_id"]),
                        model=str(invocation["model"]),
                        success=bool(invocation["success"]),
                        fallback_used=bool(invocation["fallback_used"]),
                        prompt_token_estimate=_as_int(
                            invocation.get("prompt_token_estimate")
                        )
                        or 0,
                        latency_ms=(_as_int(invocation.get("latency_ms"))),
                        error_message=(
                            str(invocation["error_message"])
                            if invocation["error_message"] is not None
                            else None
                        ),
                    )
                    event = repo.add_model_invocation_event(
                        run_id=root_run_id,
                        workflow="eval",
                        stage=str(invocation.get("stage") or "eval"),
                        provider_id=str(invocation["provider_id"]),
                        model=str(invocation["model"]),
                        attempt_index=_as_int(invocation.get("attempt_index")) or 0,
                        success=bool(invocation["success"]),
                        fallback_used=bool(invocation["fallback_used"]),
                        prompt_token_estimate=_as_int(
                            invocation.get("prompt_token_estimate")
                        )
                        or 0,
                        latency_ms=(_as_int(invocation.get("latency_ms"))),
                        error_type=(
                            str(invocation["error_type"])
                            if invocation["error_type"] is not None
                            else None
                        ),
                        provider_status_code=(
                            _as_int(invocation.get("provider_status_code"))
                        ),
                        error_message=(
                            str(invocation["error_message"])
                            if invocation["error_message"] is not None
                            else None
                        ),
                        started_at=_as_datetime(invocation.get("started_at")),
                        finished_at=_as_datetime(invocation.get("finished_at")),
                    )
                    if invocation.get("prompt_payload") is not None:
                        repo.add_payload_log(
                            run_id=root_run_id,
                            invocation_event_id=event.id,
                            workflow="eval",
                            stage=str(invocation.get("stage") or "eval"),
                            direction="prompt",
                            payload_text=str(invocation["prompt_payload"]),
                        )
                    if invocation.get("response_payload") is not None:
                        repo.add_payload_log(
                            run_id=root_run_id,
                            invocation_event_id=event.id,
                            workflow="eval",
                            stage=str(invocation.get("stage") or "eval"),
                            direction="response",
                            payload_text=str(invocation["response_payload"]),
                        )
                    if invocation.get("response_raw_payload") is not None:
                        repo.add_payload_log(
                            run_id=root_run_id,
                            invocation_event_id=event.id,
                            workflow="eval",
                            stage=str(invocation.get("stage") or "eval"),
                            direction="response_raw",
                            payload_text=str(invocation["response_raw_payload"]),
                        )
                    if invocation.get("error_payload") is not None:
                        repo.add_payload_log(
                            run_id=root_run_id,
                            invocation_event_id=event.id,
                            workflow="eval",
                            stage=str(invocation.get("stage") or "eval"),
                            direction="error",
                            payload_text=str(invocation["error_payload"]),
                        )

        score = sum(test_scores) / len(test_scores) if test_scores else 0.0
        passed = score >= config.workflows.eval.pass_threshold

        if passed:
            stop_reason = "threshold_met"
        if not allowed_all:
            stop_reason = "size_cap_exceeded"
            passed = False
        elif config.policies.require_model_success and not model_success_all:
            stop_reason = "model_invocation_failed"
            passed = False
            strict_model_success_failed = True
        elif enhance and config.workflows.enhance.run_in_eval_loop and not passed:
            enhance_result = generate_enhancement_suggestions(
                artifact.content,
                config=config,
                repo=repo,
                run_id=root_run_id,
                model_override=definition.model,
                fallback_models=definition.fallback_models,
                report_context=(
                    f"eval_id={definition.id}; iteration={iteration}; score={score:.3f}; "
                    f"threshold={config.workflows.eval.pass_threshold:.3f}"
                ),
            )

            new_suggestions = 0
            for suggestion in enhance_result.suggestions:
                repo.add_enhancement_suggestion(
                    run_id=root_run_id,
                    artifact_id=stored_artifact.id or 0,
                    suggestion=suggestion,
                    applied=False,
                    revision_summary=None,
                )
                if suggestion not in seen_suggestions:
                    seen_suggestions.add(suggestion)
                    new_suggestions += 1

            apply_allowed = config.workflows.enhance.write_mode != "suggestion-only"
            applied = False
            if apply_allowed and enhance_result.revised_content:
                applied = _write_revised_content(
                    artifact.path, enhance_result.revised_content
                )
                if applied:
                    repo.add_enhancement_suggestion(
                        run_id=root_run_id,
                        artifact_id=stored_artifact.id or 0,
                        suggestion="Applied revised content from enhance workflow.",
                        applied=True,
                        revision_summary=f"iteration={iteration}",
                    )

            changed = changed or applied or new_suggestions > 0

        repo.add_loop_progress(
            root_run_id=root_run_id,
            iteration=iteration,
            score=score,
            threshold=config.workflows.eval.pass_threshold,
            passed=passed,
            stop_reason=stop_reason,
        )

        if score > best_score:
            best_score = score
            best_iteration = iteration
            best_passed = passed
            best_stop_reason = stop_reason

        if passed or stop_reason in {"size_cap_exceeded", "model_invocation_failed"}:
            break

    if best_iteration > 1 and best_stop_reason == "max_iterations":
        best_stop_reason = "best_iteration_restored"

    return DefinitionRoundState(
        score=max(0.0, best_score),
        passed=best_passed,
        stop_reason=best_stop_reason,
        iterations_run=iterations_run,
        best_iteration=best_iteration,
        strict_model_failure=strict_model_success_failed,
        changed=changed,
        test_count=test_count,
    )


def run_eval(
    base_dir: Path,
    config: PromptBenchConfig,
    repo: ReportRepository,
    artifact_type: ArtifactType | None,
    target: str | None,
    enhance: bool,
    loop: int | None,
    concurrency: int | None = None,
    continuous: bool = False,
    continuous_max_rounds: int = CONTINUOUS_IMPROVE_MAX_ROUNDS,
) -> list[EvalOutcome]:
    definitions = load_eval_definitions(
        base_dir, config, artifact_type=artifact_type, target=target
    )
    outcomes: list[EvalOutcome] = []
    loop_limit = min(loop or 1, 20)
    concurrency_resolution = resolve_dynamic_concurrency(
        config,
        workflow="eval",
        requested=concurrency,
    )
    max_rounds = max(1, min(continuous_max_rounds, CONTINUOUS_IMPROVE_MAX_ROUNDS))

    for definition in definitions:
        root_run = repo.create_run(
            "eval", trigger="loop" if loop_limit > 1 else "manual"
        )
        config_hash = hashlib.sha256(
            config.model_dump_json().encode("utf-8")
        ).hexdigest()
        repo.add_run_context(
            run_id=root_run.id or 0,
            workflow="eval",
            artifact_type=definition.artifact_type.value,
            target=definition.target,
            config_hash=config_hash,
            require_model_success=config.policies.require_model_success,
            log_verbosity=config.policies.log_verbosity,
            requested_concurrency=(
                concurrency if concurrency is not None else config.policies.max_workers
            ),
            effective_concurrency=concurrency_resolution.effective,
            concurrency_source=concurrency_resolution.source,
        )
        artifact_root = getattr(
            config.artifacts, definition.artifact_type.value
        ).root_path
        runtime_artifact = repo.upsert_artifact(
            definition.artifact_type.value,
            definition.target,
            str((base_dir / artifact_root / definition.target).resolve()),
        )
        repo.add_enhancement_suggestion(
            run_id=root_run.id or 0,
            artifact_id=runtime_artifact.id or 0,
            suggestion=json.dumps(
                {
                    "requested": (
                        concurrency
                        if concurrency is not None
                        else config.policies.max_workers
                    ),
                    "effective": concurrency_resolution.effective,
                    "source": concurrency_resolution.source,
                }
            ),
            applied=False,
            revision_summary="runtime_concurrency",
        )
        seen_suggestions: set[str] = set()
        had_strict_failure = False
        rounds_run = 0
        best_state: DefinitionRoundState | None = None

        while True:
            rounds_run += 1
            round_state = _run_definition_round(
                base_dir=base_dir,
                config=config,
                repo=repo,
                definition=definition,
                root_run_id=root_run.id or 0,
                loop_limit=loop_limit,
                concurrency_effective=concurrency_resolution.effective,
                enhance=enhance,
                seen_suggestions=seen_suggestions,
            )

            if best_state is None or round_state.score > best_state.score:
                best_state = round_state
            had_strict_failure = had_strict_failure or round_state.strict_model_failure

            if not continuous or not round_state.changed or rounds_run >= max_rounds:
                break

        if best_state is None:
            continue

        outcomes.append(
            EvalOutcome(
                run_id=root_run.id or 0,
                eval_id=definition.id,
                score=best_state.score,
                passed=best_state.passed,
                stop_reason=best_state.stop_reason,
                iterations=best_state.iterations_run,
                best_iteration=best_state.best_iteration,
                continuous_rounds=rounds_run,
                changed=best_state.changed,
                concurrency_requested=(
                    concurrency
                    if concurrency is not None
                    else config.policies.max_workers
                ),
                concurrency_effective=concurrency_resolution.effective,
                concurrency_source=concurrency_resolution.source,
            )
        )

        repo.finish_run(
            root_run, status="failed" if had_strict_failure else "completed"
        )

    return outcomes
