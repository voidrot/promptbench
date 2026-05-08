from __future__ import annotations

from pathlib import Path


def validate_skill_file(path: Path) -> list[str]:
    """Lightweight validator for skill markdown frontmatter presence.

    Full Agent Skills specification validation can be expanded incrementally.
    """
    content = path.read_text(encoding="utf-8")
    findings: list[str] = []

    if not content.startswith("---\n"):
        findings.append("missing_frontmatter")
        return findings

    if "name:" not in content:
        findings.append("missing_name")
    if "description:" not in content:
        findings.append("missing_description")
    return findings
