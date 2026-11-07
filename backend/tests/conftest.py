import os
import tempfile

# Configure before the app (and its cached settings / DB engine) is imported.
# Tests run on an empty PostgreSQL: GRE_TEST_DATABASE_URL if set (e.g. a CI
# service container), otherwise a throwaway local server (pgserver). Never the
# developer's Supabase database.
if os.environ.get("GRE_TEST_DATABASE_URL"):
    os.environ["GRE_DATABASE_URL"] = os.environ["GRE_TEST_DATABASE_URL"]
else:
    import pgserver

    _pg = pgserver.get_server(tempfile.mkdtemp(), cleanup_mode="stop")
    os.environ["GRE_DATABASE_URL"] = _pg.get_uri()
os.environ["GRE_ENV_FILE"] = ""  # ignore the developer's backend/.env
os.environ["GRE_AI_ENABLED"] = "false"
os.environ["GRE_AUTH_MODE"] = "dev"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session
