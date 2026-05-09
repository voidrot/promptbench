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


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _resolve_skill_directory(candidate: Path) -> ArtifactDocument:
    skill_md = candidate / "SKILL.md"
    if not skill_md.exists() or not skill_md.is_file():
        raise FileNotFoundError(f"Skill target directory missing SKILL.md: {candidate}")

    sections: list[str] = [_read_text_file(skill_md)]
    for references_dir_name in ("references", "refrences"):
        references_dir = candidate / references_dir_name
        if not references_dir.exists() or not references_dir.is_dir():
            continue
        for ref_file in sorted(
            path for path in references_dir.rglob("*") if path.is_file()
        ):
            relative_ref = ref_file.relative_to(candidate)
            try:
                ref_content = _read_text_file(ref_file)
            except UnicodeDecodeError:
                continue
            sections.append(f"## Reference: {relative_ref}\n\n{ref_content}")

    content = "\n\n".join(sections)
    lines = content.splitlines()
    return ArtifactDocument(
        artifact_type=ArtifactType.SKILLS.value,
        name=candidate.name,
        path=skill_md.resolve(),
        content=content,
        line_count=len(lines),
        token_count_estimate=_estimate_tokens(content),
    )


def _resolve_directory_target(candidate: Path, artifact_type: ArtifactType) -> Path:
    if artifact_type == ArtifactType.AGENTS:
        agent_md = candidate / "AGENT.md"
        if agent_md.exists() and agent_md.is_file():
            return agent_md
    raise IsADirectoryError(f"Target must be a file, got directory: {candidate}")


def resolve_artifact(
    base_dir: Path, config: PromptBenchConfig, artifact_type: ArtifactType, target: str
) -> ArtifactDocument:
    root = base_dir / _artifact_root(config, artifact_type)
    candidate = Path(target)
    if not candidate.is_absolute():
        candidate = root / candidate

    if candidate.is_dir():
        if artifact_type == ArtifactType.SKILLS:
            return _resolve_skill_directory(candidate)
        candidate = _resolve_directory_target(candidate, artifact_type)
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
