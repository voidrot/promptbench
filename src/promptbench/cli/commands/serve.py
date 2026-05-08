from __future__ import annotations

from pathlib import Path

from promptbench.config.loader import load_config
from promptbench.web.app import create_app


def serve_command(
    host: str = "127.0.0.1",
    port: int = 8080,
    config: Path = Path("promptbench.yaml"),
    repo: Path = Path("."),
) -> None:
    cfg = load_config(config)
    project_root = (repo / cfg.project.root).resolve()
    db_path = (project_root / cfg.output.database_path).resolve()
    app = create_app(db_path, config=cfg)
    app.run(host=host, port=port)
