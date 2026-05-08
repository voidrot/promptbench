from promptbench.config.schema import (
    PromptBenchConfig,
    ProviderConfig,
    WorkflowProviderConfig,
)
from promptbench.provider.runtime import (
    resolve_dynamic_concurrency,
    resolve_workflow_model_chain,
)
from promptbench.reporting.database import init_database, session_for
from promptbench.reporting.repository import ReportRepository
from promptbench.workflows.eval import run_eval


def test_dynamic_concurrency_local_defaults_to_two() -> None:
    cfg = PromptBenchConfig()
    cfg.policies.max_workers = 4
    cfg.providers.registry = {
        "llmstudio": ProviderConfig(
            kind="openai-compatible",
            base_url="http://localhost:1234/v1",
            api_key_env="LLMSTUDIO_API_KEY",
            max_concurrency=None,
        )
    }
    cfg.providers.workflows = {
        "eval": WorkflowProviderConfig(
            provider_kind="llmstudio",
            model="llmstudio/nvidia/nemotron-3-nano-4b",
            fallback_models=[],
        )
    }

    resolved = resolve_dynamic_concurrency(cfg, workflow="eval", requested=None)
    assert resolved.effective == 2


def test_dynamic_concurrency_honors_explicit_cli() -> None:
    cfg = PromptBenchConfig()
    resolved = resolve_dynamic_concurrency(cfg, workflow="eval", requested=3)
    assert resolved.effective == 3
    assert resolved.source == "cli"


def test_dynamic_concurrency_uses_provider_cap() -> None:
    cfg = PromptBenchConfig()
    cfg.policies.max_workers = 5
    cfg.providers.registry = {
        "llmstudio": ProviderConfig(
            kind="openai-compatible",
            base_url="http://localhost:1234/v1",
            api_key_env="LLMSTUDIO_API_KEY",
            max_concurrency=3,
        )
    }
    cfg.providers.workflows = {
        "eval": WorkflowProviderConfig(
            provider_kind="llmstudio",
            model="llmstudio/nvidia/nemotron-3-nano-4b",
            fallback_models=[],
        )
    }

    resolved = resolve_dynamic_concurrency(cfg, workflow="eval", requested=None)
    assert resolved.effective == 3
    assert resolved.source == "provider.max_concurrency"


def test_eval_outcome_exposes_concurrency(tmp_path) -> None:
    repo_root = tmp_path
    (repo_root / "skills").mkdir(parents=True, exist_ok=True)
    (repo_root / "skills" / "sample.md").write_text("alpha\n", encoding="utf-8")
    (repo_root / ".promptbench" / "evals").mkdir(parents=True, exist_ok=True)
    (repo_root / ".promptbench" / "evals" / "sample.eval.yaml").write_text(
        """
id: sample
artifact_type: skills
target: sample.md
prompt: alpha
""",
        encoding="utf-8",
    )

    cfg = PromptBenchConfig()
    cfg.project.root = "."
    cfg.artifacts.skills.root_path = "skills/"
    cfg.policies.require_model_success = False
    cfg.providers.registry = {}
    cfg.providers.workflows = {}

    engine = init_database(repo_root / ".promptbench" / "promptbench.db")
    with session_for(engine) as session:
        repository = ReportRepository(session)
        outcomes = run_eval(
            base_dir=repo_root,
            config=cfg,
            repo=repository,
            artifact_type=None,
            target=None,
            enhance=False,
            loop=1,
            concurrency=2,
        )

    assert outcomes
    assert outcomes[0].concurrency_effective == 2
    assert outcomes[0].concurrency_source == "cli"


def test_model_chain_tries_primary_first_then_fallbacks() -> None:
    cfg = PromptBenchConfig()
    cfg.providers.registry = {
        "llmstudio": ProviderConfig(
            kind="openai-compatible",
            base_url="http://localhost:1234/v1",
            api_key_env="LLMSTUDIO_API_KEY",
        )
    }
    cfg.providers.workflows = {
        "eval": WorkflowProviderConfig(
            provider_kind="llmstudio",
            model="llmstudio/primary",
            fallback_models=["llmstudio/fallback-1", "llmstudio/fallback-2"],
        )
    }

    chain = resolve_workflow_model_chain(cfg, workflow="eval")
    assert [p.model_name for p in chain] == ["primary", "fallback-1", "fallback-2"]


def test_model_chain_allows_no_fallbacks() -> None:
    cfg = PromptBenchConfig()
    cfg.providers.registry = {
        "llmstudio": ProviderConfig(
            kind="openai-compatible",
            base_url="http://localhost:1234/v1",
            api_key_env="LLMSTUDIO_API_KEY",
        )
    }
    cfg.providers.workflows = {
        "eval": WorkflowProviderConfig(
            provider_kind="llmstudio",
            model="llmstudio/primary",
            fallback_models=None,
        )
    }

    chain = resolve_workflow_model_chain(cfg, workflow="eval")
    assert [p.model_name for p in chain] == ["primary"]


def test_model_chain_randomizes_with_seed() -> None:
    cfg = PromptBenchConfig()
    cfg.policies.model_random_seed = 1337
    cfg.providers.registry = {
        "llmstudio": ProviderConfig(
            kind="openai-compatible",
            base_url="http://localhost:1234/v1",
            api_key_env="LLMSTUDIO_API_KEY",
        )
    }
    cfg.providers.workflows = {
        "eval": WorkflowProviderConfig(
            provider_kind="llmstudio",
            model="llmstudio/primary",
            fallback_models=["llmstudio/fallback-1", "llmstudio/fallback-2"],
            randomize_model=True,
        )
    }

    chain_a = resolve_workflow_model_chain(
        cfg,
        workflow="eval",
        randomization_key="test-a",
    )
    chain_b = resolve_workflow_model_chain(
        cfg,
        workflow="eval",
        randomization_key="test-a",
    )
    chain_c = resolve_workflow_model_chain(
        cfg,
        workflow="eval",
        randomization_key="test-b",
    )

    names_a = [p.model_name for p in chain_a]
    names_b = [p.model_name for p in chain_b]
    names_c = [p.model_name for p in chain_c]
    assert names_a == names_b
    assert sorted(names_a) == ["fallback-1", "fallback-2", "primary"]
    assert sorted(names_c) == ["fallback-1", "fallback-2", "primary"]
