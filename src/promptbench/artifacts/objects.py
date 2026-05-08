from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactDocument:
    artifact_type: str
    name: str
    path: Path
    content: str
    line_count: int
    token_count_estimate: int
