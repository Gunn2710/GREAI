import uuid

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from pydantic import ValidationError
from sqlalchemy import inspect, text

from app.secrets_config import Secrets
from app.db import BASELINE_REVISION, Base, alembic_config, engine, init_db, make_engine

HEAD = ScriptDirectory.from_config(alembic_config()).get_current_head()


def legacy_database(name: str):
    """A database as the old create_all setup left it: the baseline schema
    (revision 0001) with no Alembic bookkeeping."""
    from alembic import command

    db_name = f"{name}_{uuid.uuid4().hex[:8]}"
    with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
        conn.execute(text(f"CREATE DATABASE {db_name}"))
    db = make_engine(engine.url.set(database=db_name).render_as_string(hide_password=False))
    command.upgrade(alembic_config(db.url.render_as_string(hide_password=False)), BASELINE_REVISION)
    with db.begin() as conn:
        conn.execute(text("DROP TABLE alembic_version"))
    return db


def test_migrations_match_models(client):
    """Schema changes must come with a migration: no diff between the
    migrated database and app/models.py."""
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_head_revision_applied(client):
    with engine.connect() as conn:
        assert MigrationContext.configure(conn).get_current_revision() == HEAD


def test_pre_alembic_database_is_adopted():
    """A dev database made by the old create_all setup is stamped at the
    baseline and upgraded in place, keeping its data."""
    legacy = legacy_database("legacy")
    with legacy.begin() as conn:
        conn.execute(text("INSERT INTO profiles (user_id, daily_new_words, created_at) VALUES ('old-user', 7, CURRENT_TIMESTAMP)"))
    init_db(legacy)
    with legacy.connect() as conn:
        assert MigrationContext.configure(conn).get_current_revision() == HEAD
        assert conn.execute(text("SELECT daily_new_words FROM profiles")).scalar() == 7
    assert BASELINE_REVISION == "0001"


def test_interrupted_first_migration_is_recovered():
    """App tables plus an empty alembic_version table (a first run that died
    before recording a revision) must be adopted, not re-created."""
    legacy = legacy_database("interrupted")
    with legacy.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
    init_db(legacy)
    with legacy.connect() as conn:
        assert MigrationContext.configure(conn).get_current_revision() == HEAD


def test_row_level_security(client):
    with engine.connect() as conn:
        rows = dict(conn.execute(text(
            "SELECT relname, relrowsecurity FROM pg_class "
            "WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'"
        )).all())
    tables = set(inspect(engine).get_table_names())
    assert tables and all(rows[t] for t in tables), rows


def test_only_postgres_urls_are_accepted():
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Secrets(_env_file=None, database_url="sqlite:///./gre_prep.db")
    assert Secrets(_env_file=None, database_url="postgresql://u:p@h:5432/db").database_url


def test_secrets_never_show_in_errors_or_reprs():
    with pytest.raises(ValidationError) as err:
        Secrets(_env_file=None, database_url="mysql://user:hunter2@h/db")
    assert "hunter2" not in str(err.value)
    s = Secrets(_env_file=None, database_url="postgresql://u:hunter2@h/db", anthropic_api_key="sk-ant-xyz")
    assert "hunter2" not in repr(s) and "sk-ant-xyz" not in repr(s)


DIRECT = "postgresql://postgres:pw@db.abcdefgh.supabase.co:5432/postgres"
POOLER = "postgresql://postgres.abcdefgh:pw@aws-0-us-east-1.pooler.supabase.com:6543/postgres"


def test_vercel_rejects_the_ipv6_only_supabase_host(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(ValidationError, match="Transaction pooler") as err:
        Secrets(_env_file=None, GRE_DATABASE_URL=DIRECT)
    assert "pw" not in str(err.value)
    assert Secrets(_env_file=None, GRE_DATABASE_URL=POOLER).database_url.get_secret_value() == POOLER


def test_direct_host_is_fine_off_vercel(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    assert Secrets(_env_file=None, GRE_DATABASE_URL=DIRECT).database_url.get_secret_value() == DIRECT


def test_vercel_engine_keeps_no_idle_connections(monkeypatch):
    from sqlalchemy.pool import NullPool

    monkeypatch.setenv("VERCEL", "1")
    assert isinstance(make_engine(POOLER).pool, NullPool)
    monkeypatch.delenv("VERCEL")
    assert not isinstance(make_engine(POOLER).pool, NullPool)
