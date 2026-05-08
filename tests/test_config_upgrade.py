from __future__ import annotations

from pathlib import Path

import yaml

from promptbench.config.schema import LATEST_CONFIG_VERSION
from promptbench.config.upgrade import upgrade_config_file


def test_upgrade_config_v1_to_v2_adds_defaults(tmp_path: Path) -> None:
    cfg_path = tmp_path / "promptbench.yaml"
    cfg_path.write_text(
        """
version: 1
project:
  name: test
  root: .
objects:
  defaults: {}
  skills: {}
  prompts: {}
  agents: {}
  tools: {}
artifacts:
  skills:
    root_path: skills/
  prompts:
    root_path: prompts/
  agents:
    root_path: agents/
  tools:
    root_path: tools/
providers:
  registry: {}
  workflows:
    review:
      provider_kind: openai
      model: openai/gpt-4.1-mini
    eval:
      provider_kind: openai
      model: openai/gpt-4.1-mini
    enhance:
      provider_kind: openai
      model: openai/gpt-4.1-mini
workflows:
  review: {}
  eval: {}
  enhance: {}
output: {}
policies: {}
""",
        encoding="utf-8",
    )

    cfg, changes, warnings = upgrade_config_file(cfg_path)

    assert cfg.version == LATEST_CONFIG_VERSION
    assert "set version=2" in changes
    assert cfg.providers.workflows["judge"].model == "openai/gpt-4.1-mini"
    assert cfg.providers.workflows["eval"].randomize_model is False
    assert cfg.policies.model_random_seed is None
    assert warnings
    assert "provider_kind" in warnings[0]

    loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert loaded["version"] == LATEST_CONFIG_VERSION
    assert "judge" in loaded["providers"]["workflows"]


def test_upgrade_config_is_noop_when_latest(tmp_path: Path) -> None:
    cfg_path = tmp_path / "promptbench.yaml"
    cfg_path.write_text(
        """
version: 2
project:
  name: test
  root: .
objects:
  defaults: {}
  skills: {}
  prompts: {}
  agents: {}
  tools: {}
  instructions: {}
artifacts:
  skills:
    root_path: skills/
  prompts:
    root_path: prompts/
  agents:
    root_path: agents/
  tools:
    root_path: tools/
  instructions:
    root_path: instructions/
providers:
  registry: {}
  workflows:
    review:
      provider_kind: openai
      model: openai/gpt-4.1-mini
      randomize_model: false
    eval:
      provider_kind: openai
      model: openai/gpt-4.1-mini
      randomize_model: false
    judge:
      provider_kind: openai
      model: openai/gpt-4.1-mini
      randomize_model: false
    enhance:
      provider_kind: openai
      model: openai/gpt-4.1-mini
      randomize_model: false
workflows:
  review: {}
  eval: {}
  enhance: {}
output: {}
policies:
  model_random_seed: null
""",
        encoding="utf-8",
    )

    cfg, changes, warnings = upgrade_config_file(cfg_path)

    assert cfg.version == LATEST_CONFIG_VERSION
    assert not changes
    assert warnings


def test_upgrade_removes_provider_kind_keys(tmp_path: Path) -> None:
    cfg_path = tmp_path / "promptbench.yaml"
    cfg_path.write_text(
        """
version: 1
project:
  name: test
  root: .
objects:
  defaults: {}
  skills: {}
  prompts: {}
  agents: {}
  tools: {}
artifacts:
  skills:
    root_path: skills/
  prompts:
    root_path: prompts/
  agents:
    root_path: agents/
  tools:
    root_path: tools/
providers:
  registry: {}
  workflows:
    review:
      provider_kind: openai
      model: openai/gpt-4.1-mini
    eval:
      provider_kind: openai
      model: openai/gpt-4.1-mini
    enhance:
      provider_kind: openai
      model: openai/gpt-4.1-mini
workflows:
  review: {}
  eval: {}
  enhance: {}
output: {}
policies: {}
""",
        encoding="utf-8",
    )

    _cfg, changes, _warnings = upgrade_config_file(cfg_path)
    assert any("removed providers.workflows.review.provider_kind" in c for c in changes)
    assert any("removed providers.workflows.eval.provider_kind" in c for c in changes)
    assert any(
        "removed providers.workflows.enhance.provider_kind" in c for c in changes
    )

    loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    for workflow in ("review", "eval", "judge", "enhance"):
        assert "provider_kind" not in loaded["providers"]["workflows"][workflow]
