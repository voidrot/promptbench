from __future__ import annotations

import json
from typing import Any

from promptbench.config.schema import PromptBenchConfig


_LEVELS = {
    "quiet": 0,
    "normal": 1,
    "debug": 2,
    "trace": 3,
}


def _level_value(level: str) -> int:
    return _LEVELS.get(level, _LEVELS["normal"])


def should_log(config: PromptBenchConfig, level: str) -> bool:
    configured = config.policies.log_verbosity
    return _level_value(configured) >= _level_value(level)


def log_line(config: PromptBenchConfig, level: str, message: str) -> None:
    if should_log(config, level):
        print(f"[{level}] {message}")


def preview_payload(payload: Any, max_chars: int = 1200) -> str:
    if payload is None:
        return "<none>"
    if isinstance(payload, str):
        raw = payload
    else:
        try:
            raw = json.dumps(payload, ensure_ascii=True)
        except Exception:  # noqa: BLE001
            raw = str(payload)
    if len(raw) <= max_chars:
        return raw
    return raw[:max_chars] + "...<truncated>"


def serialize_payload(payload: Any) -> str:
    if payload is None:
        return "<none>"
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, ensure_ascii=True)
    except Exception:  # noqa: BLE001
        return str(payload)


def extract_raw_response(run_result: Any) -> str | None:
    all_messages_json = getattr(run_result, "all_messages_json", None)
    if callable(all_messages_json):
        try:
            return serialize_payload(all_messages_json())
        except Exception:  # noqa: BLE001
            return None

    all_messages = getattr(run_result, "all_messages", None)
    if callable(all_messages):
        try:
            return serialize_payload(all_messages())
        except Exception:  # noqa: BLE001
            return None

    raw_output = getattr(run_result, "raw_output", None)
    if raw_output is not None:
        return serialize_payload(raw_output)

    return None


def extract_error_details(exc: Exception) -> dict[str, Any]:
    status_code = None
    if hasattr(exc, "status_code"):
        try:
            status_code = int(getattr(exc, "status_code"))
        except Exception:  # noqa: BLE001
            status_code = None
    if status_code is None and hasattr(exc, "response"):
        response = getattr(exc, "response")
        if response is not None and hasattr(response, "status_code"):
            try:
                status_code = int(getattr(response, "status_code"))
            except Exception:  # noqa: BLE001
                status_code = None

    return {
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "provider_status_code": status_code,
    }
