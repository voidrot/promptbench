from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from promptbench.config.loader import _resolve_env
from promptbench.config.schema import LATEST_CONFIG_VERSION, PromptBenchConfig


DEPRECATED_SETTINGS: dict[str, str] = {
    "providers.workflows.review.provider_kind": (
        "Deprecated for routing behavior: review now falls back to "
        "providers.workflows.judge. Keep review for primary reviewer and configure judge explicitly."
    ),
    "providers.workflows.eval.provider_kind": (
        "Deprecated for routing behavior: eval scoring now prefers providers.workflows.judge. "
        "Configure judge explicitly for grading consistency."
    ),
}


def _get_nested(data: dict[str, Any], path: str) -> Any:
    node: Any = data
    for key in path.split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _set_nested_default(data: dict[str, Any], path: str, value: Any) -> bool:
    keys = path.split(".")
    node = data
    for key in keys[:-1]:
        next_node = node.get(key)
        if not isinstance(next_node, dict):
            next_node = {}
            node[key] = next_node
        node = next_node
    leaf = keys[-1]
    if leaf in node:
        return False
    node[leaf] = value
    return True


def _upgrade_v1_to_v2(raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    changes: list[str] = []

    if _set_nested_default(raw, "objects.instructions", {}):
        changes.append("added objects.instructions")
    if _set_nested_default(raw, "artifacts.instructions.root_path", "instructions/"):
        changes.append("added artifacts.instructions.root_path")
    if _set_nested_default(raw, "providers.workflows.judge.provider_kind", "openai"):
        changes.append("added providers.workflows.judge.provider_kind")
    if _set_nested_default(
        raw, "providers.workflows.judge.model", "openai/gpt-4.1-mini"
    ):
        changes.append("added providers.workflows.judge.model")
    if _set_nested_default(raw, "providers.workflows.judge.fallback_models", []):
        changes.append("added providers.workflows.judge.fallback_models")
    if _set_nested_default(raw, "providers.workflows.judge.randomize_model", False):
        changes.append("added providers.workflows.judge.randomize_model")

    for workflow in ("review", "eval", "enhance"):
        if _set_nested_default(
            raw, f"providers.workflows.{workflow}.randomize_model", False
        ):
            changes.append(f"added providers.workflows.{workflow}.randomize_model")

    if _set_nested_default(raw, "policies.model_random_seed", None):
        changes.append("added policies.model_random_seed")

    raw["version"] = 2
    changes.append("set version=2")
    return raw, changes


def collect_deprecation_warnings(raw: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for path, message in DEPRECATED_SETTINGS.items():
        value = _get_nested(raw, path)
        if value is not None:
            warnings.append(f"{path}: {message}")
    return warnings


def upgrade_config_file(
    path: str | Path,
) -> tuple[PromptBenchConfig, list[str], list[str]]:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config not found: {cfg_path}")

    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("Config must be a YAML object.")

    old_version = int(raw.get("version", 1))
    changes: list[str] = []

    if old_version < 2:
        raw, migration_changes = _upgrade_v1_to_v2(raw)
        changes.extend(migration_changes)

    if old_version > LATEST_CONFIG_VERSION:
        raise ValueError(
            f"Config version {old_version} is newer than supported version {LATEST_CONFIG_VERSION}."
        )

    warnings = collect_deprecation_warnings(raw)

    cfg_path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )

    validated = PromptBenchConfig.model_validate(_resolve_env(raw))
    return validated, changes, warnings
