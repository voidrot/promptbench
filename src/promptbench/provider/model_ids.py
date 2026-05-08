from __future__ import annotations


def parse_model_id(value: str) -> tuple[str, str]:
    if "/" not in value:
        raise ValueError(
            f"Invalid model id '{value}'. Expected '<provider-id>/<model-name>'."
        )
    provider_id, model_name = value.split("/", 1)
    if not provider_id or not model_name:
        raise ValueError(
            f"Invalid model id '{value}'. Expected '<provider-id>/<model-name>'."
        )
    return provider_id, model_name
