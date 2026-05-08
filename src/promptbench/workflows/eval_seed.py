from __future__ import annotations

import json
from typing import cast

from pydantic_ai import Agent

from promptbench.config.schema import ArtifactType, EvalTest, PromptBenchConfig
from promptbench.provider.runtime import (
    provider_openai_env,
    resolve_workflow_model_chain,
)
from promptbench.runtime_logging import extract_error_details
from promptbench.workflows.pydantic_models import EvalSeedModelOutput

_MAX_PROMPT_CHARS = 9000


def _seed_agent(model_name: str) -> Agent[None, EvalSeedModelOutput]:
    return cast(
        Agent[None, EvalSeedModelOutput],
        Agent(
            f"openai:{model_name}",
            output_type=EvalSeedModelOutput,
            system_prompt=(
                "Generate initial eval tests for a merged artifact. Return 3 to 5 tests. "
                "Each test must include a concise prompt. IDs should be short and stable."
            ),
        ),
    )


def _excerpt_text(text: str, *, limit: int = _MAX_PROMPT_CHARS) -> str:
    if len(text) <= limit:
        return text
    keep_head = limit // 2
    keep_tail = limit - keep_head
    return f"{text[:keep_head]}\n\n... [truncated] ...\n\n{text[-keep_tail:]}"


def _normalize_seed_tests(seed: EvalSeedModelOutput) -> list[EvalTest]:
    tests: list[EvalTest] = []
    for idx, test in enumerate(seed.tests, start=1):
        prompt = (test.prompt or "").strip()
        if not prompt:
            continue
        test_id = (test.id or "").strip() or f"seed-{idx}"
        tests.append(
            EvalTest(
                id=test_id,
                prompt=prompt,
                expected=dict(test.expected),
                references=list(test.references),
            )
        )
    return tests


def generate_eval_seed_tests(
    *,
    config: PromptBenchConfig,
    artifact_type: ArtifactType,
    merged_target: str,
    source_targets: list[str],
    merged_content: str,
) -> list[EvalTest]:
    model_chain = resolve_workflow_model_chain(config, workflow="eval")
    if not model_chain:
        raise RuntimeError(
            "No providers.workflows.eval model chain configured for eval test generation."
        )

    payload = {
        "artifact_type": artifact_type.value,
        "merged_target": merged_target,
        "source_targets": source_targets,
        "merged_excerpt": _excerpt_text(merged_content),
        "instructions": [
            "Return between 3 and 5 tests.",
            "Cover baseline quality, edge handling, and correctness.",
            "Keep prompts specific and non-redundant.",
        ],
    }
    serialized_payload = json.dumps(payload, ensure_ascii=True)

    last_error: str | None = None
    for provider in model_chain:
        try:
            with provider_openai_env(provider):
                result = _seed_agent(provider.model_name).run_sync(serialized_payload)
            tests = _normalize_seed_tests(result.output)
            if len(tests) < 3:
                raise RuntimeError(
                    "Model generated too few valid eval tests; expected at least 3."
                )
            return tests[:5]
        except Exception as exc:  # noqa: BLE001
            details = extract_error_details(exc)
            last_error = str(details["error_message"])

    raise RuntimeError(
        "Unable to generate initial eval tests via model chain. "
        f"Last error: {last_error or 'unknown error'}"
    )


__all__ = ["generate_eval_seed_tests"]
