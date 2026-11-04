import tempfile

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.db import BASELINE_REVISION, Base, alembic_config, engine, init_db, make_engine

HEAD = ScriptDirectory.from_config(alembic_config()).get_current_head()


def legacy_database(name: str):
    """A database as the old create_all setup left it: the baseline schema
    (revision 0001) with no Alembic bookkeeping."""
    from alembic import command

    db = make_engine(f"sqlite:///{tempfile.mkdtemp()}/{name}.db")
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


def test_row_level_security_on_postgres(client):
    if engine.dialect.name != "postgresql":
        return
    with engine.connect() as conn:
        rows = dict(conn.execute(text(
            "SELECT relname, relrowsecurity FROM pg_class "
            "WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'"
        )).all())
    tables = set(inspect(engine).get_table_names())
    assert tables and all(rows[t] for t in tables), rows
