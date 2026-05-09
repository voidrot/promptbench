from __future__ import annotations

import hashlib
import re
from pathlib import Path

import typer
import yaml

from promptbench.artifacts.resolver import resolve_artifact
from promptbench.cli.commands.eval import eval_command
from promptbench.config.loader import load_config
from promptbench.config.schema import ArtifactType, EvalTest
from promptbench.workflows.eval_seed import generate_eval_seed_tests


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    return normalized or "merged"


def _dedupe_targets(targets: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for target in targets:
        if target in seen:
            continue
        seen.add(target)
        deduped.append(target)
    return deduped


def _resolve_suffix(paths: list[Path]) -> str:
    if not paths:
        raise typer.BadParameter("No artifact paths were resolved.")
    suffixes = {path.suffix for path in paths}
    if len(suffixes) > 1:
        raise typer.BadParameter("All merged targets must use the same file extension.")
    return paths[0].suffix


def _merged_filename(base_name: str, targets: list[str], suffix: str) -> str:
    digest = hashlib.sha256("\n".join(targets).encode("utf-8")).hexdigest()[:8]
    return f"{_safe_name(base_name)}-{digest}{suffix}"


def _compose_merged_content(sources: list[tuple[str, str]]) -> str:
    sections: list[str] = []
    for target, content in sources:
        header = f"--- source: {target} ---"
        section_body = content if content.endswith("\n") else f"{content}\n"
        sections.append(f"{header}\n{section_body}")
    return "\n".join(sections).rstrip() + "\n"


def _seed_to_yaml_tests(seed_tests: list[EvalTest]) -> list[dict[str, object]]:
    yaml_tests: list[dict[str, object]] = []
    for index, test in enumerate(seed_tests, start=1):
        row: dict[str, object] = {
            "id": test.id or f"seed-{index}",
            "prompt": (test.prompt or "").strip(),
        }
        if test.expected:
            row["expected"] = dict(test.expected)
        if test.references:
            row["references"] = list(test.references)
        yaml_tests.append(row)
    return yaml_tests


def _resolve_merge_sources(
    *,
    project_root: Path,
    cfg,
    artifact_type: ArtifactType,
    targets: list[str],
):
    source_documents = []
    for target in targets:
        try:
            source_documents.append(
                resolve_artifact(project_root, cfg, artifact_type, target)
            )
        except (FileNotFoundError, IsADirectoryError) as exc:
            if artifact_type == ArtifactType.SKILLS:
                raise typer.BadParameter(
                    f"Invalid skills target '{target}'. For skill packages, pass the skill directory path/name and ensure it contains SKILL.md; optional references may live in references/ or refrences/."
                ) from exc
            raise typer.BadParameter(f"Invalid target '{target}': {exc}") from exc
    return source_documents


def eval_merge_command(
    *,
    artifact_type: ArtifactType,
    targets: list[str],
    name: str | None = None,
    concurrency: int | None = None,
    require_model_success: bool = True,
    randomize_model: bool | None = None,
    model_random_seed: int | None = None,
    log_verbosity: str | None = None,
    config: Path = Path("promptbench.yaml"),
    repo: Path = Path("."),
) -> None:
    unique_targets = _dedupe_targets(targets)
    if len(unique_targets) < 2:
        raise typer.BadParameter(
            "eval-merge requires at least two unique targets for the selected artifact type."
        )

    cfg = load_config(config)
    if log_verbosity is not None:
        cfg.policies.log_verbosity = log_verbosity
    cfg.policies.require_model_success = require_model_success
    if randomize_model is not None:
        for workflow_name in ("eval", "judge", "enhance"):
            workflow_cfg = cfg.providers.workflows.get(workflow_name)
            if workflow_cfg is not None:
                workflow_cfg.randomize_model = randomize_model
    if model_random_seed is not None:
        cfg.policies.model_random_seed = model_random_seed

    project_root = (repo / cfg.project.root).resolve()

    source_documents = _resolve_merge_sources(
        project_root=project_root,
        cfg=cfg,
        artifact_type=artifact_type,
        targets=unique_targets,
    )
    suffix = _resolve_suffix([doc.path for doc in source_documents])
    merged_base_name = name or source_documents[0].name
    merged_filename = _merged_filename(merged_base_name, unique_targets, suffix)

    artifact_root = project_root / getattr(cfg.artifacts, artifact_type.value).root_path
    merged_dir = artifact_root / "_merged"
    merged_path = merged_dir / merged_filename
    merged_target = str(Path("_merged") / merged_filename)

    merged_content = _compose_merged_content(
        [
            (source, document.content)
            for source, document in zip(unique_targets, source_documents)
        ]
    )
    seed_tests = generate_eval_seed_tests(
        config=cfg,
        artifact_type=artifact_type,
        merged_target=merged_target,
        source_targets=unique_targets,
        merged_content=merged_content,
    )
    if len(seed_tests) < 3:
        raise typer.BadParameter(
            "Generated eval tests are insufficient; expected at least 3."
        )

    eval_id = f"merged-{artifact_type.value}-{Path(merged_filename).stem}"
    eval_definition = {
        "id": eval_id,
        "artifact_type": artifact_type.value,
        "target": merged_target,
        "tests": _seed_to_yaml_tests(seed_tests),
    }

    evals_dir = project_root / ".promptbench" / "evals"
    eval_path = evals_dir / f"{Path(merged_filename).stem}.eval.yaml"

    merged_dir.mkdir(parents=True, exist_ok=True)
    evals_dir.mkdir(parents=True, exist_ok=True)
    merged_path.write_text(merged_content, encoding="utf-8")
    eval_path.write_text(
        yaml.safe_dump(eval_definition, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )

    typer.echo(f"merged_artifact={merged_path}")
    typer.echo(f"merged_eval_definition={eval_path}")

    eval_command(
        artifact_type=artifact_type,
        target=merged_target,
        enhance=False,
        loop=10,
        concurrency=concurrency,
        continuous=False,
        require_model_success=require_model_success,
        randomize_model=randomize_model,
        model_random_seed=model_random_seed,
        log_verbosity=log_verbosity,
        config=config,
        repo=repo,
    )


__all__ = ["eval_merge_command"]
