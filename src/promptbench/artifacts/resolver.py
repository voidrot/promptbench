from __future__ import annotations

from pathlib import Path

from promptbench.artifacts.objects import ArtifactDocument
from promptbench.config.schema import ArtifactType, PromptBenchConfig


def _estimate_tokens(text: str) -> int:
    # Deterministic coarse estimate for gating and reporting.
    if not text:
        return 0
    return max(1, len(text) // 4)


def _artifact_root(config: PromptBenchConfig, artifact_type: ArtifactType) -> str:
    art_cfg = getattr(config.artifacts, artifact_type.value)
    return art_cfg.root_path


def resolve_artifact(
    base_dir: Path, config: PromptBenchConfig, artifact_type: ArtifactType, target: str
) -> ArtifactDocument:
    root = base_dir / _artifact_root(config, artifact_type)
    candidate = Path(target)
    if not candidate.is_absolute():
        candidate = root / candidate

    if candidate.is_dir():
        raise IsADirectoryError(f"Target must be a file, got directory: {candidate}")
    if not candidate.exists():
        raise FileNotFoundError(f"Artifact not found: {candidate}")

    content = candidate.read_text(encoding="utf-8")
    lines = content.splitlines()
    return ArtifactDocument(
        artifact_type=artifact_type.value,
        name=candidate.stem,
        path=candidate.resolve(),
        content=content,
        line_count=len(lines),
        token_count_estimate=_estimate_tokens(content),
    )
