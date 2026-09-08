from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401 - register every ORM model before metadata setup
from app.db.base import Base
from app.db.dependencies import get_db
from app.main import app
from app.agents.research.mock_research_agent import MockResearchAgent
from app.api.v1.endpoints.research_chat import get_research_agent_provider
from app.core.security import create_access_token
from app.models.user import SysUser


load_dotenv(Path(__file__).resolve().parents[1] / ".env.test.example", override=False)
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
print(f"Testing database URL: {TEST_DATABASE_URL}")
if not TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL must point to the dedicated MySQL test database. "
        "See .env.test.example."
    )

test_database_name = make_url(TEST_DATABASE_URL).database
test_database_driver = make_url(TEST_DATABASE_URL).drivername
if test_database_driver != "mysql+pymysql":
    raise RuntimeError("Pytest requires a MySQL database URL using mysql+pymysql.")
if test_database_name != "smart_literacy_stewardship_test":
    raise RuntimeError(
        "Pytest refuses to run unless TEST_DATABASE_URL targets "
        "smart_literacy_stewardship_test."
    )

engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def prepare_test_database():
    """Create only the dedicated test schema, then remove it after the suite."""
    with engine.connect() as connection:
        version = str(connection.scalar(text("SELECT VERSION()")))
    if not version.startswith("8."):
        raise RuntimeError(f"Pytest requires MySQL 8; connected server is {version}.")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def db() -> Session:
    """Give each case a fresh MySQL schema because API writes commit explicitly."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def teacher(db: Session) -> SysUser:
    user = SysUser(
        username="teacher",
        password="secret",
        display_name="Teacher",
        role="TEACHER",
        status=1,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def other(db: Session) -> SysUser:
    user = SysUser(
        username="other",
        password="secret",
        display_name="Other",
        role="TEACHER",
        status=1,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def auth_headers(teacher: SysUser) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(teacher.username)}"}


@pytest.fixture()
def client(db: Session):
    def override_get_db():
        yield db

    def override_research_agent_provider() -> MockResearchAgent:
        return MockResearchAgent()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_research_agent_provider] = (
        override_research_agent_provider
    )
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
