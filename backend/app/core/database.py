"""SQLAlchemy engine/session wiring (infrastructure boundary)."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()
_connect_args = (
    {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(_settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create the schema directly (fast, no ALTERs). For tests only — the app
    boots via `run_migrations()` so schema changes actually apply."""
    from app.infrastructure.db import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)


def run_migrations() -> None:
    """Bring the database up to `head`. Used at app startup: unlike create_all,
    a migration ALTERs existing tables, so a new column lands on an old DB."""
    from alembic import command
    from alembic.config import Config

    backend_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(cfg, "head")  # env.py reads the URL from Settings
