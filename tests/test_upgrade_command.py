from __future__ import annotations

from pathlib import Path

from promptbench.cli.commands.upgrade import upgrade_command


def test_upgrade_command_updates_v1_config(tmp_path: Path) -> None:
    cfg_path = tmp_path / "promptbench.yaml"
    cfg_path.write_text(
        """
version: 1
project:
  name: t
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

    upgrade_command(cfg_path)

    upgraded = cfg_path.read_text(encoding="utf-8")
    assert "version: 2" in upgraded
    assert "judge:" in upgraded
    assert "model_random_seed: null" in upgraded
