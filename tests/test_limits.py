from promptbench.config.schema import (
    ArtifactType,
    ObjectLimits,
    ObjectsConfig,
    PromptBenchConfig,
)
from promptbench.workflows.common import resolve_effective_limits, within_limits


def test_limits_resolution_order() -> None:
    cfg = PromptBenchConfig(
        objects=ObjectsConfig(
            defaults=ObjectLimits(max_line_count=100, max_token_count=200),
            skills=ObjectLimits(max_line_count=150),
        )
    )
    effective = resolve_effective_limits(
        cfg, ArtifactType.SKILLS, ObjectLimits(max_token_count=175)
    )
    assert effective.max_line_count == 150
    assert effective.max_token_count == 175


def test_within_limits() -> None:
    limits = ObjectLimits(max_line_count=10, max_token_count=30)
    assert within_limits(10, 30, limits)
    assert not within_limits(11, 30, limits)
    assert not within_limits(10, 31, limits)
