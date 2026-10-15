"""Test fixtures.

Tests run against PostgreSQL by default (TEST_DATABASE_URL, defaulting to the
dev cluster from scripts/dev-postgres.sh). Each test runs inside a transaction
that is rolled back afterwards, so tests can freely mutate menu data.
"""

import os

os.environ.setdefault(
    "TEST_DATABASE_URL", "postgresql+psycopg://reschat:reschat@127.0.0.1:5433/reschatbot_test"
)
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["ASSISTANT_DEMO_MODE"] = "true"  # never call a real LLM from tests
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["GROQ_API_KEY"] = ""
os.environ["XAI_API_KEY"] = ""
os.environ["RATE_LIMIT_CHAT_PER_MINUTE"] = "1000"
os.environ["RATE_LIMIT_SEARCH_PER_MINUTE"] = "1000"
os.environ["ADMIN_API_KEY"] = "test-admin-key"
os.environ["ENVIRONMENT"] = "test"
os.environ["SERVER_OCR_ENABLED"] = "true"  # exercise the server OCR path too

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import Base, get_db  # noqa: E402
from app.llm.factory import get_provider  # noqa: E402
from app.main import app  # noqa: E402
from app.ratelimit import limiter  # noqa: E402
from app.seed.seed import seed  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(os.environ["TEST_DATABASE_URL"], future=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        seed(s)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture()
def client(db):
    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_provider] = lambda: None
    limiter.reset()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def chat(client, message, conversation_id=None, slug="fernwood", **extra):
    body = {"message": message, "conversation_id": conversation_id, **extra}
    r = client.post(f"/api/restaurants/{slug}/assistant/chat", json=body)
    assert r.status_code == 200, r.text
    return r.json()
