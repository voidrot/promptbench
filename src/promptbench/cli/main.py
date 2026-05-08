from __future__ import annotations

from pathlib import Path

import typer

from promptbench.cli.commands.eval import eval_command
from promptbench.cli.commands.eval_all import eval_all_command
from promptbench.cli.commands.eval_merge import eval_merge_command
from promptbench.cli.commands.init import init_command
from promptbench.cli.commands.report import report_command
from promptbench.cli.commands.review import review_command
from promptbench.cli.commands.serve import serve_command
from promptbench.config.schema import ArtifactType


app = typer.Typer(help="PromptBench CLI")


def _validate_log_verbosity(value: str | None) -> str | None:
    if value is None:
        return None
    allowed = {"quiet", "normal", "debug", "trace"}
    if value not in allowed:
        raise typer.BadParameter(
            "--log-verbosity must be one of: quiet, normal, debug, trace"
        )
    return value


@app.command("init")
def init(
    config: Path = typer.Option(
        Path("promptbench.yaml"), "--config", help="Path to config file."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite if file exists."),
) -> None:
    init_command(config=config, force=force)


@app.command("review")
def review(
    artifact_type: ArtifactType,
    target: str,
    require_model_success: bool | None = typer.Option(
        None,
        "--require-model-success/--no-require-model-success",
        help="Require at least one successful model invocation; otherwise fail run.",
    ),
    randomize_model: bool | None = typer.Option(
        None,
        "--randomize-model/--no-randomize-model",
        help="Override model randomization across review/judge workflows.",
    ),
    model_random_seed: int | None = typer.Option(
        None,
        "--model-random-seed",
        help="Seed for deterministic model randomization.",
    ),
    log_verbosity: str | None = typer.Option(
        None,
        "--log-verbosity",
        help="Logging verbosity: quiet|normal|debug|trace.",
    ),
    config: Path = typer.Option(
        Path("promptbench.yaml"), "--config", help="Path to config file."
    ),
    repo: Path = typer.Option(Path("."), "--repo", help="Project root."),
) -> None:
    review_command(
        artifact_type=artifact_type,
        target=target,
        require_model_success=require_model_success,
        randomize_model=randomize_model,
        model_random_seed=model_random_seed,
        log_verbosity=_validate_log_verbosity(log_verbosity),
        config=config,
        repo=repo,
    )


@app.command("eval")
def eval(
    artifact_type: ArtifactType | None = typer.Argument(None),
    target: str | None = typer.Argument(None),
    enhance: bool = typer.Option(False, "--enhance", help="Enable enhance step."),
    loop: int | None = typer.Option(None, "--loop", help="Max loop iterations."),
    concurrency: int | None = typer.Option(
        None,
        "--concurrency",
        help="Requested eval concurrency; auto-tuned when omitted.",
    ),
    continuous: bool = typer.Option(
        False,
        "--continuous",
        help="Keep running improve rounds while changes keep being generated.",
    ),
    continuous_max_rounds: int = typer.Option(
        6,
        "--continuous-max-rounds",
        help="Hard cap for continuous improve rounds (max 6).",
    ),
    require_model_success: bool = typer.Option(
        True,
        "--require-model-success/--no-require-model-success",
        help="Require at least one successful model invocation; otherwise fail run.",
    ),
    randomize_model: bool | None = typer.Option(
        None,
        "--randomize-model/--no-randomize-model",
        help="Override model randomization across eval/judge/enhance workflows.",
    ),
    model_random_seed: int | None = typer.Option(
        None,
        "--model-random-seed",
        help="Seed for deterministic model randomization.",
    ),
    log_verbosity: str | None = typer.Option(
        None,
        "--log-verbosity",
        help="Logging verbosity: quiet|normal|debug|trace.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Write JSON trajectory report file.",
    ),
    config: Path = typer.Option(
        Path("promptbench.yaml"), "--config", help="Path to config file."
    ),
    repo: Path = typer.Option(Path("."), "--repo", help="Project root."),
) -> None:
    eval_command(
        artifact_type=artifact_type,
        target=target,
        enhance=enhance,
        loop=loop,
        concurrency=concurrency,
        continuous=continuous,
        continuous_max_rounds=continuous_max_rounds,
        require_model_success=require_model_success,
        randomize_model=randomize_model,
        model_random_seed=model_random_seed,
        log_verbosity=_validate_log_verbosity(log_verbosity),
        output=output,
        config=config,
        repo=repo,
    )


@app.command("eval-all")
def eval_all(
    artifact_type: ArtifactType,
    enhance: bool = typer.Option(False, "--enhance", help="Enable enhance step."),
    loop: int | None = typer.Option(None, "--loop", help="Max loop iterations."),
    concurrency: int | None = typer.Option(
        None,
        "--concurrency",
        help="Requested eval concurrency; auto-tuned when omitted.",
    ),
    continuous: bool = typer.Option(
        False,
        "--continuous",
        help="Keep running improve rounds while changes keep being generated.",
    ),
    continuous_max_rounds: int = typer.Option(
        6,
        "--continuous-max-rounds",
        help="Hard cap for continuous improve rounds (max 6).",
    ),
    require_model_success: bool = typer.Option(
        True,
        "--require-model-success/--no-require-model-success",
        help="Require at least one successful model invocation; otherwise fail run.",
    ),
    randomize_model: bool | None = typer.Option(
        None,
        "--randomize-model/--no-randomize-model",
        help="Override model randomization across eval/judge/enhance workflows.",
    ),
    model_random_seed: int | None = typer.Option(
        None,
        "--model-random-seed",
        help="Seed for deterministic model randomization.",
    ),
    log_verbosity: str | None = typer.Option(
        None,
        "--log-verbosity",
        help="Logging verbosity: quiet|normal|debug|trace.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Write aggregate JSON trajectory report file.",
    ),
    config: Path = typer.Option(
        Path("promptbench.yaml"), "--config", help="Path to config file."
    ),
    repo: Path = typer.Option(Path("."), "--repo", help="Project root."),
) -> None:
    eval_all_command(
        artifact_type=artifact_type,
        enhance=enhance,
        loop=loop,
        concurrency=concurrency,
        continuous=continuous,
        continuous_max_rounds=continuous_max_rounds,
        require_model_success=require_model_success,
        randomize_model=randomize_model,
        model_random_seed=model_random_seed,
        log_verbosity=_validate_log_verbosity(log_verbosity),
        output=output,
        config=config,
        repo=repo,
    )


@app.command("eval-merge")
def eval_merge(
    artifact_type: ArtifactType,
    targets: list[str] = typer.Argument(..., help="Two or more artifact targets."),
    name: str | None = typer.Option(
        None,
        "--name",
        help="Optional base name for merged outputs.",
    ),
    concurrency: int | None = typer.Option(
        None,
        "--concurrency",
        help="Requested eval concurrency; auto-tuned when omitted.",
    ),
    require_model_success: bool = typer.Option(
        True,
        "--require-model-success/--no-require-model-success",
        help="Require at least one successful model invocation; otherwise fail run.",
    ),
    randomize_model: bool | None = typer.Option(
        None,
        "--randomize-model/--no-randomize-model",
        help="Override model randomization across eval/judge/enhance workflows.",
    ),
    model_random_seed: int | None = typer.Option(
        None,
        "--model-random-seed",
        help="Seed for deterministic model randomization.",
    ),
    log_verbosity: str | None = typer.Option(
        None,
        "--log-verbosity",
        help="Logging verbosity: quiet|normal|debug|trace.",
    ),
    config: Path = typer.Option(
        Path("promptbench.yaml"), "--config", help="Path to config file."
    ),
    repo: Path = typer.Option(Path("."), "--repo", help="Project root."),
) -> None:
    eval_merge_command(
        artifact_type=artifact_type,
        targets=targets,
        name=name,
        concurrency=concurrency,
        require_model_success=require_model_success,
        randomize_model=randomize_model,
        model_random_seed=model_random_seed,
        log_verbosity=_validate_log_verbosity(log_verbosity),
        config=config,
        repo=repo,
    )


@app.command("report")
def report(
    since: str | None = typer.Option(
        None, "--since", help="Filter horizon (reserved)."
    ),
    format: str = typer.Option(
        "json", "--format", help="Output format: json|markdown."
    ),
    config: Path = typer.Option(
        Path("promptbench.yaml"), "--config", help="Path to config file."
    ),
    repo: Path = typer.Option(Path("."), "--repo", help="Project root."),
) -> None:
    if format not in {"json", "markdown"}:
        raise typer.BadParameter("--format must be 'json' or 'markdown'.")
    report_command(since=since, format=format, config=config, repo=repo)


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Host bind for Flask server."),
    port: int = typer.Option(8080, "--port", help="Port for Flask server."),
    config: Path = typer.Option(
        Path("promptbench.yaml"), "--config", help="Path to config file."
    ),
    repo: Path = typer.Option(Path("."), "--repo", help="Project root."),
) -> None:
    serve_command(host=host, port=port, config=config, repo=repo)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
