from pathlib import Path

import pytest

from promptbench.artifacts.resolver import resolve_artifact
from promptbench.config.schema import ArtifactType, PromptBenchConfig


def _config() -> PromptBenchConfig:
    return PromptBenchConfig.model_validate(
        {
            "version": 2,
            "project": {"name": "test", "root": "."},
            "objects": {
                "defaults": {},
                "skills": {},
                "prompts": {},
                "agents": {},
                "tools": {},
                "instructions": {},
            },
            "artifacts": {
                "skills": {"root_path": "skills/"},
                "prompts": {"root_path": "prompts/"},
                "agents": {"root_path": "agents/"},
                "tools": {"root_path": "tools/"},
                "instructions": {"root_path": "instructions/"},
            },
            "providers": {
                "default_kind": "openai-compatible",
                "defaults": {
                    "timeout_seconds": 60,
                    "max_retries": 3,
                    "temperature": 0.2,
                },
                "registry": {},
                "workflows": {},
            },
            "workflows": {
                "review": {"enabled": True, "max_findings": 25},
                "eval": {
                    "enabled": True,
                    "metrics": [],
                    "pass_threshold": 0.8,
                    "definition_mode": "discover",
                    "discover_path": "evals/",
                    "inline": [],
                },
                "enhance": {
                    "enabled": True,
                    "write_mode": "suggestion-only",
                    "run_in_eval_loop": True,
                },
            },
            "output": {
                "database_path": ".promptbench/promptbench.db",
                "overwrite": False,
                "reports_dir": ".promptbench/reports",
            },
            "policies": {
                "fail_on_severity": "error",
                "fail_on_score_below": 0.7,
                "max_workers": 1,
                "require_model_success": False,
                "log_verbosity": "normal",
                "model_random_seed": None,
            },
        }
    )


def test_resolve_skill_directory_reads_skill_and_references(tmp_path: Path) -> None:
    cfg = _config()
    skill_dir = tmp_path / "skills" / "mise"
    refs_dir = skill_dir / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "# Mise Skill\n\nCore content", encoding="utf-8"
    )
    (refs_dir / "usage.md").write_text("Use this skill like so.", encoding="utf-8")

    doc = resolve_artifact(tmp_path, cfg, ArtifactType.SKILLS, "mise")

    assert doc.name == "mise"
    assert doc.path == (skill_dir / "SKILL.md").resolve()
    assert "# Mise Skill" in doc.content
    assert "## Reference: references/usage.md" in doc.content
    assert "Use this skill like so." in doc.content


def test_resolve_skill_directory_requires_skill_md(tmp_path: Path) -> None:
    cfg = _config()
    refs_dir = tmp_path / "skills" / "mise" / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)
    (refs_dir / "usage.md").write_text("ref", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="missing SKILL.md"):
        resolve_artifact(tmp_path, cfg, ArtifactType.SKILLS, "mise")


def test_resolve_skill_directory_reads_legacy_refrences_dir(tmp_path: Path) -> None:
    cfg = _config()
    skill_dir = tmp_path / "skills" / "mise"
    legacy_refs_dir = skill_dir / "refrences"
    legacy_refs_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Legacy Skill", encoding="utf-8")
    (legacy_refs_dir / "notes.md").write_text("legacy reference", encoding="utf-8")

    doc = resolve_artifact(tmp_path, cfg, ArtifactType.SKILLS, "mise")

    assert "## Reference: refrences/notes.md" in doc.content
    assert "legacy reference" in doc.content
