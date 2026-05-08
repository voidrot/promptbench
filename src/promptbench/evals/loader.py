from __future__ import annotations

from pathlib import Path

import yaml

from promptbench.config.schema import ArtifactType, EvalDefinition, PromptBenchConfig


def _read_eval_file(path: Path) -> EvalDefinition:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return EvalDefinition.model_validate(raw)


def load_eval_definitions(
    base_dir: Path,
    config: PromptBenchConfig,
    artifact_type: ArtifactType | None = None,
    target: str | None = None,
) -> list[EvalDefinition]:
    definitions: list[EvalDefinition] = []
    seen: set[tuple[str, str, str]] = set()

    def add_definition(definition: EvalDefinition) -> None:
        key = (
            definition.artifact_type.value,
            definition.target,
            definition.id,
        )
        if key in seen:
            return
        seen.add(key)
        definitions.append(definition)

    inline_defs = list(config.workflows.eval.inline)
    for at in (
        ArtifactType.SKILLS,
        ArtifactType.PROMPTS,
        ArtifactType.AGENTS,
        ArtifactType.TOOLS,
    ):
        inline_defs.extend(getattr(config.artifacts, at.value).evals)

    for definition in inline_defs:
        if artifact_type and definition.artifact_type != artifact_type:
            continue
        if target and definition.target != target:
            continue
        add_definition(definition)

    eval_dir = base_dir / ".promptbench" / "evals"
    if eval_dir.exists():
        for file_path in sorted(eval_dir.glob("*.eval.yaml")):
            definition = _read_eval_file(file_path)
            if artifact_type and definition.artifact_type != artifact_type:
                continue
            if target and definition.target != target:
                continue
            add_definition(definition)

    types_to_scan = (
        [artifact_type]
        if artifact_type is not None
        else [
            ArtifactType.SKILLS,
            ArtifactType.PROMPTS,
            ArtifactType.AGENTS,
            ArtifactType.TOOLS,
        ]
    )

    for at in types_to_scan:
        artifact_root = base_dir / getattr(config.artifacts, at.value).root_path
        if artifact_root.exists():
            for file_path in sorted(artifact_root.glob("*.eval.yaml")):
                definition = _read_eval_file(file_path)
                if definition.artifact_type != at:
                    continue
                if target and definition.target != target:
                    continue
                add_definition(definition)

    return definitions
