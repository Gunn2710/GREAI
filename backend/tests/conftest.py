import os
import tempfile

# Configure before the app (and its cached settings / DB engine) is imported.
# GRE_TEST_POSTGRES=1 runs the suite on a throwaway PostgreSQL (pgserver).
_tmp = tempfile.mkdtemp()
if os.environ.get("GRE_TEST_POSTGRES"):
    import pgserver

    _pg = pgserver.get_server(_tmp, cleanup_mode="stop")
    os.environ["GRE_DATABASE_URL"] = _pg.get_uri()
else:
    os.environ["GRE_DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
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
