from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from promptbench.config.schema import PromptBenchConfig


def _resolve_env(value: Any) -> Any:
    if isinstance(value, str):
        if value.startswith("${") and value.endswith("}"):
            name = value[2:-1]
            return os.environ.get(name, "")
        if value.isupper() and "_" in value and value in os.environ:
            return os.environ[value]
        return value
    if isinstance(value, list):
        return [_resolve_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_env(item) for key, item in value.items()}
    return value


def load_config(path: str | Path) -> PromptBenchConfig:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config not found: {cfg_path}")

    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    resolved = _resolve_env(raw)
    return PromptBenchConfig.model_validate(resolved)
