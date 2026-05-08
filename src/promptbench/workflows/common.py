from __future__ import annotations

from promptbench.config.schema import ArtifactType, ObjectLimits, PromptBenchConfig


def resolve_effective_limits(
    config: PromptBenchConfig,
    artifact_type: ArtifactType,
    eval_override: ObjectLimits | None,
) -> ObjectLimits:
    defaults = config.objects.defaults
    by_type = getattr(config.objects, artifact_type.value)

    max_line_count = defaults.max_line_count
    max_token_count = defaults.max_token_count

    if by_type.max_line_count is not None:
        max_line_count = by_type.max_line_count
    if by_type.max_token_count is not None:
        max_token_count = by_type.max_token_count

    if eval_override is not None:
        if eval_override.max_line_count is not None:
            max_line_count = eval_override.max_line_count
        if eval_override.max_token_count is not None:
            max_token_count = eval_override.max_token_count

    return ObjectLimits(max_line_count=max_line_count, max_token_count=max_token_count)


def within_limits(line_count: int, token_count: int, limits: ObjectLimits) -> bool:
    if limits.max_line_count is not None and line_count > limits.max_line_count:
        return False
    if limits.max_token_count is not None and token_count > limits.max_token_count:
        return False
    return True
