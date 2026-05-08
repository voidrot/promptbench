from __future__ import annotations

import os
import random
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from promptbench.config.schema import PromptBenchConfig
from promptbench.provider.model_ids import parse_model_id


@dataclass
class ProviderResolution:
    provider_id: str
    model_name: str
    base_url: str
    api_key_env: str
    kind: str


@dataclass
class ConcurrencyResolution:
    requested: int
    effective: int
    source: str


def resolve_provider(config: PromptBenchConfig, model_id: str) -> ProviderResolution:
    provider_id, model_name = parse_model_id(model_id)
    provider = config.providers.registry.get(provider_id)
    if provider is None:
        raise KeyError(f"Unknown provider '{provider_id}' in model '{model_id}'.")
    return ProviderResolution(
        provider_id=provider_id,
        model_name=model_name,
        base_url=provider.base_url,
        api_key_env=provider.api_key_env,
        kind=provider.kind,
    )


def resolve_workflow_model_chain(
    config: PromptBenchConfig,
    workflow: str,
    model_override: str | None = None,
    fallback_overrides: list[str] | None = None,
    randomize_model: bool | None = None,
    randomization_key: str | None = None,
) -> list[ProviderResolution]:
    workflow_cfg = config.providers.workflows.get(workflow)
    configured_primary = workflow_cfg.model if workflow_cfg is not None else None
    primary = model_override if model_override is not None else configured_primary
    if primary is None or not str(primary).strip():
        return []
    if fallback_overrides is not None:
        fallbacks = [item for item in fallback_overrides if str(item).strip()]
    else:
        configured_fallbacks = (
            workflow_cfg.fallback_models if workflow_cfg is not None else None
        )
        if configured_fallbacks is None:
            fallbacks = []
        else:
            fallbacks = [item for item in configured_fallbacks if str(item).strip()]

    ordered_ids: list[str] = []
    for model_id in [primary, *fallbacks]:
        if model_id not in ordered_ids:
            ordered_ids.append(model_id)

    workflow_randomize = (
        workflow_cfg.randomize_model if workflow_cfg is not None else False
    )
    should_randomize = (
        randomize_model if randomize_model is not None else workflow_randomize
    )
    if should_randomize and len(ordered_ids) > 1:
        seed_value = config.policies.model_random_seed
        if seed_value is None:
            random.shuffle(ordered_ids)
        else:
            key = randomization_key or workflow
            rng = random.Random(f"{seed_value}:{workflow}:{key}")
            rng.shuffle(ordered_ids)

    resolved: list[ProviderResolution] = []
    for model_id in ordered_ids:
        try:
            resolved.append(resolve_provider(config, model_id))
        except KeyError:
            continue
    return resolved


def resolve_dynamic_concurrency(
    config: PromptBenchConfig,
    workflow: str,
    requested: int | None = None,
) -> ConcurrencyResolution:
    if requested is not None:
        effective = max(1, min(requested, 8))
        return ConcurrencyResolution(
            requested=requested,
            effective=effective,
            source="cli",
        )

    policy_workers = max(1, min(config.policies.max_workers, 8))
    model_chain = resolve_workflow_model_chain(config, workflow=workflow)
    if not model_chain:
        return ConcurrencyResolution(
            requested=policy_workers,
            effective=policy_workers,
            source="policies.max_workers",
        )

    primary = model_chain[0]
    if primary.provider_id in config.providers.registry:
        provider_cfg = config.providers.registry[primary.provider_id]
        if provider_cfg.max_concurrency is not None:
            effective = max(1, min(provider_cfg.max_concurrency, 8, policy_workers))
            return ConcurrencyResolution(
                requested=policy_workers,
                effective=effective,
                source="provider.max_concurrency",
            )

    local = "localhost" in primary.base_url or "127.0.0.1" in primary.base_url
    provider_cap = 2 if local else 1
    effective = max(1, min(policy_workers, provider_cap))
    source = "provider-local-cap" if local else "provider-remote-cap"
    return ConcurrencyResolution(
        requested=policy_workers,
        effective=effective,
        source=source,
    )


@contextmanager
def provider_openai_env(provider: ProviderResolution) -> Iterator[None]:
    prev_base_url = os.environ.get("OPENAI_BASE_URL")
    prev_api_key = os.environ.get("OPENAI_API_KEY")

    os.environ["OPENAI_BASE_URL"] = provider.base_url
    configured_api_key = os.environ.get(provider.api_key_env)
    if configured_api_key is not None:
        os.environ["OPENAI_API_KEY"] = configured_api_key
    else:
        # OpenAI-compatible clients require a key even for local endpoints.
        # Use a deterministic placeholder to allow LMStudio/local gateways.
        os.environ["OPENAI_API_KEY"] = "dummy"

    try:
        yield
    finally:
        if prev_base_url is None:
            os.environ.pop("OPENAI_BASE_URL", None)
        else:
            os.environ["OPENAI_BASE_URL"] = prev_base_url

        if prev_api_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = prev_api_key
