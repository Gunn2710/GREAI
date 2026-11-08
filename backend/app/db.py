import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.secrets_config import get_secrets

BACKEND_DIR = Path(__file__).resolve().parents[1]
BASELINE_REVISION = "0001"


class Base(DeclarativeBase):
    pass


def normalize_url(url: str) -> str:
    """Accept the connection string as Supabase shows it ("postgresql://..."),
    and point it at the installed psycopg 3 driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def make_engine(url: str) -> Engine:
    # Supabase's transaction pooler (port 6543) can't hold prepared statements
    # across transactions; turning them off is harmless elsewhere.
    options: dict = {"connect_args": {"prepare_threshold": None}, "pool_pre_ping": True}
    if os.environ.get("VERCEL"):
        # Serverless instances are many, short-lived and frozen between requests:
        # an idle pool in each one would only use up the pooler's connection
        # limit. Supabase's pooler does the pooling instead.
        options["poolclass"] = NullPool
    return create_engine(normalize_url(url), **options)


engine = make_engine(get_secrets().database_url.get_secret_value())
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def alembic_config(url: str | None = None):
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    if url:
        cfg.attributes["database_url"] = url
    return cfg


def init_db(target: Engine | None = None) -> None:
    """Bring the schema to the latest migration.

    Databases created before migrations existed (the old create_all dev setup)
    match the baseline revision exactly, so they are stamped and then upgraded.
    """
    from alembic import command
    from alembic.migration import MigrationContext

    from app import models  # noqa: F401  (registers tables)

    target = target or engine
    cfg = alembic_config(target.url.render_as_string(hide_password=False))
    app_tables = set(inspect(target).get_table_names()) - {"alembic_version"}
    with target.connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()
    # App tables but no recorded revision: a pre-migrations database (an empty
    # alembic_version table, e.g. from an interrupted first run, counts too).
    if app_tables and current is None:
        command.stamp(cfg, BASELINE_REVISION)
    command.upgrade(cfg, "head")
