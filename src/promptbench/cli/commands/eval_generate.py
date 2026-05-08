from __future__ import annotations

import hashlib
from pathlib import Path

import typer
import yaml

from promptbench.artifacts.resolver import resolve_artifact
from promptbench.config.loader import load_config
from promptbench.config.schema import ArtifactType, EvalTest
from promptbench.workflows.eval_seed import generate_eval_seed_tests


def _seed_to_yaml_tests(seed_tests: list[EvalTest]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, test in enumerate(seed_tests, start=1):
        row: dict[str, object] = {
            "id": test.id or f"seed-{index}",
            "prompt": (test.prompt or "").strip(),
        }
        if test.expected:
            row["expected"] = dict(test.expected)
        if test.references:
            row["references"] = list(test.references)
        rows.append(row)
    return rows


def eval_generate_command(
    *,
    artifact_type: ArtifactType,
    target: str,
    name: str | None = None,
    randomize_model: bool | None = None,
    model_random_seed: int | None = None,
    log_verbosity: str | None = None,
    config: Path = Path("promptbench.yaml"),
    repo: Path = Path("."),
) -> None:
    cfg = load_config(config)
    if log_verbosity is not None:
        cfg.policies.log_verbosity = log_verbosity
    if randomize_model is not None:
        for workflow_name in ("eval", "judge"):
            workflow_cfg = cfg.providers.workflows.get(workflow_name)
            if workflow_cfg is not None:
                workflow_cfg.randomize_model = randomize_model
    if model_random_seed is not None:
        cfg.policies.model_random_seed = model_random_seed

    project_root = (repo / cfg.project.root).resolve()
    document = resolve_artifact(project_root, cfg, artifact_type, target)

    effective_target = target
    if Path(target).is_absolute():
        artifact_root = (
            project_root / getattr(cfg.artifacts, artifact_type.value).root_path
        )
        effective_target = str(document.path.relative_to(artifact_root))

    source_targets = [effective_target]
    seed_tests = generate_eval_seed_tests(
        config=cfg,
        artifact_type=artifact_type,
        merged_target=effective_target,
        source_targets=source_targets,
        merged_content=document.content,
    )
    if len(seed_tests) < 3:
        raise typer.BadParameter(
            "Generated eval tests are insufficient; expected at least 3."
        )

    base_name = name or document.name
    digest = hashlib.sha256(
        f"{artifact_type.value}:{effective_target}".encode("utf-8")
    ).hexdigest()[:8]
    eval_stem = f"{base_name}-{digest}"

    eval_definition = {
        "id": f"seed-{artifact_type.value}-{eval_stem}",
        "artifact_type": artifact_type.value,
        "target": effective_target,
        "tests": _seed_to_yaml_tests(seed_tests),
    }

    evals_dir = project_root / ".promptbench" / "evals"
    evals_dir.mkdir(parents=True, exist_ok=True)
    eval_path = evals_dir / f"{eval_stem}.eval.yaml"
    eval_path.write_text(
        yaml.safe_dump(eval_definition, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )

    typer.echo(f"generated_eval_definition={eval_path}")
    typer.echo(f"artifact_target={effective_target}")


__all__ = ["eval_generate_command"]
