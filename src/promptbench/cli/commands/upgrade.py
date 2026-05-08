from __future__ import annotations

from pathlib import Path

import typer

from promptbench.config.upgrade import upgrade_config_file


def upgrade_command(config: Path = Path("promptbench.yaml")) -> None:
    _, changes, warnings = upgrade_config_file(config)

    if changes:
        typer.echo(f"Upgraded {config} with {len(changes)} change(s):")
        for change in changes:
            typer.echo(f"  - {change}")
    else:
        typer.echo(f"{config} is already up to date.")

    if warnings:
        typer.echo("Deprecated settings detected:")
        for warning in warnings:
            typer.echo(f"  - {warning}")


__all__ = ["upgrade_command"]
