from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from promptbench.config.schema import (
    ArtifactType,
    PromptBenchConfig,
)
from promptbench.workflows import eval_seed
from promptbench.workflows.pydantic_models import (
    EvalSeedModelOutput,
    EvalSeedTestOutput,
)


@contextmanager
def _noop_provider_env(_provider: object):
    yield


def test_generate_eval_seed_tests_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = PromptBenchConfig()

    class DummyAgent:
        def run_sync(self, _payload: str):
            return SimpleNamespace(
                output=EvalSeedModelOutput(
                    tests=[
                        EvalSeedTestOutput(id="t1", prompt="check clarity"),
                        EvalSeedTestOutput(id="t2", prompt="check structure"),
                        EvalSeedTestOutput(id="t3", prompt="check constraints"),
                    ]
                )
            )

    monkeypatch.setattr(
        eval_seed,
        "resolve_workflow_model_chain",
        lambda *_args, **_kwargs: [SimpleNamespace(model_name="fake-model")],
    )
    monkeypatch.setattr(eval_seed, "provider_openai_env", _noop_provider_env)
    monkeypatch.setattr(eval_seed, "_seed_agent", lambda _model_name: DummyAgent())

    tests = eval_seed.generate_eval_seed_tests(
        config=cfg,
        artifact_type=ArtifactType.SKILLS,
        merged_target="_merged/out.md",
        source_targets=["a.md", "b.md"],
        merged_content="x" * 15000,
    )

    assert len(tests) == 3
    assert tests[0].id == "t1"
    assert tests[0].prompt == "check clarity"


def test_generate_eval_seed_tests_requires_provider_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = PromptBenchConfig()
    monkeypatch.setattr(
        eval_seed,
        "resolve_workflow_model_chain",
        lambda *_args, **_kwargs: [],
    )

    with pytest.raises(RuntimeError, match="No providers.workflows.eval model chain"):
        eval_seed.generate_eval_seed_tests(
            config=cfg,
            artifact_type=ArtifactType.SKILLS,
            merged_target="_merged/out.md",
            source_targets=["a.md", "b.md"],
            merged_content="content",
        )


def test_generate_eval_seed_tests_rejects_too_few_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = PromptBenchConfig()

    class DummyAgent:
        def run_sync(self, _payload: str):
            return SimpleNamespace(
                output=EvalSeedModelOutput(
                    tests=[EvalSeedTestOutput(id="t1", prompt="only one")]
                )
            )

    monkeypatch.setattr(
        eval_seed,
        "resolve_workflow_model_chain",
        lambda *_args, **_kwargs: [SimpleNamespace(model_name="fake-model")],
    )
    monkeypatch.setattr(eval_seed, "provider_openai_env", _noop_provider_env)
    monkeypatch.setattr(eval_seed, "_seed_agent", lambda _model_name: DummyAgent())

    with pytest.raises(RuntimeError, match="Unable to generate initial eval tests"):
        eval_seed.generate_eval_seed_tests(
            config=cfg,
            artifact_type=ArtifactType.SKILLS,
            merged_target="_merged/out.md",
            source_targets=["a.md", "b.md"],
            merged_content="content",
        )
