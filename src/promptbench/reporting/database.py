from __future__ import annotations

from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine


def sqlite_url(db_path: Path) -> str:
    return f"sqlite:///{db_path}"


def init_database(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        sqlite_url(db_path), connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    return engine


def session_for(engine) -> Session:
    return Session(engine)
