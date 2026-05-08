from pathlib import Path

from promptbench.reporting.database import init_database, session_for
from promptbench.reporting.repository import ReportRepository
from promptbench.web.app import create_app


def test_web_routes_render(tmp_path: Path) -> None:
    db_path = tmp_path / "promptbench.db"
    engine = init_database(db_path)
    with session_for(engine) as session:
        repo = ReportRepository(session)
        run = repo.create_run("review")
        artifact = repo.upsert_artifact("skills", "my-skill", "skills/my-skill.md")
        repo.link_run_artifact(run.id or 0, artifact.id or 0)
        repo.finish_run(run)

    app = create_app(db_path)
    client = app.test_client()

    assert client.get("/").status_code == 200
    assert client.get("/runs").status_code == 200
    assert client.get("/runs/1").status_code == 200
    assert client.get("/artifacts").status_code == 200
    assert client.get("/artifacts/1").status_code == 200
    assert client.get("/metrics").status_code == 200
    assert client.get("/api/charts/score-trend").status_code == 200
    assert (
        client.get(
            "/runs?since=2026-01-01&until=2027-01-01&sort=id&dir=asc"
        ).status_code
        == 200
    )
    detail = client.get("/runs/1")
    assert detail.status_code == 200
    assert b"Failure Diagnostics" in detail.data
    assert b"Healthcheck models" in detail.data


def test_healthcheck_models_endpoint_without_config(tmp_path: Path) -> None:
    db_path = tmp_path / "promptbench.db"
    _ = init_database(db_path)

    app = create_app(db_path)
    client = app.test_client()
    response = client.get("/api/healthcheck/models")
    assert response.status_code == 400
