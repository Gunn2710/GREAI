"""Alembic environment.

The database URL comes from the app settings (GRE_DATABASE_URL), or from
config.attributes["database_url"] when migrations run inside the app.

    alembic upgrade head                      # apply migrations
    alembic revision --autogenerate -m "..."  # after changing app/models.py
"""
from alembic import context

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.config import get_settings
from app.db import Base, make_engine, normalize_url

config = context.config
target_metadata = Base.metadata


def database_url() -> str:
    return normalize_url(config.attributes.get("database_url") or get_settings().database_url)


def run_migrations_offline() -> None:
    url = database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = make_engine(database_url())
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite can't ALTER most things in place; batch mode rebuilds tables.
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
