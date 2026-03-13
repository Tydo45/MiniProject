import os
import subprocess
import time
import uuid
from collections.abc import Callable, Generator

import jwt
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from lobby.config import get_environment_database_url, get_settings, reset_settings_cache
from lobby.db import get_db
from lobby.main import app
from lobby.realtime import get_notifier, manager

load_dotenv()
reset_settings_cache()
database_url = get_environment_database_url()


class FakeNotifier:
    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, dict]] = []

    async def notify_user(self, user_id: uuid.UUID, message: dict) -> None:
        self.calls.append((user_id, message))


@pytest.fixture(scope="session", autouse=True)
def postgres_container() -> Generator[None, None, None]:
    subprocess.run(["docker", "rm", "-f", "lobby-test-postgres"], check=False)
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "lobby-test-postgres",
            "-p",
            "5432:5432",
            "-e",
            "POSTGRES_DB=ci",
            "-e",
            "POSTGRES_USER=ci",
            "-e",
            "POSTGRES_PASSWORD=ci",
            "postgres:16",
        ],
        check=True,
    )

    time.sleep(5)

    alembic_env = os.environ.copy()
    alembic_env["DATABASE_URL"] = database_url
    subprocess.run(["alembic", "upgrade", "head"], check=True, env=alembic_env)

    yield

    subprocess.run(["docker", "rm", "-f", "lobby-test-postgres"], check=False)


@pytest.fixture
def db_session(postgres_container: None) -> Generator[Session, None, None]:
    engine = create_engine(database_url)
    session_local = sessionmaker(bind=engine)

    connection = engine.connect()
    transaction = connection.begin()
    session = session_local(bind=connection)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture
def fake_notifier() -> FakeNotifier:
    return FakeNotifier()


@pytest.fixture
def client(db_session: Session, fake_notifier: FakeNotifier) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_notifier] = lambda: fake_notifier

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def websocket_client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    manager._connections.clear()
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        manager._connections.clear()


@pytest.fixture
def auth_headers() -> Callable[[uuid.UUID], dict[str, str]]:
    settings = get_settings()

    def make_auth_headers(user_id: uuid.UUID) -> dict[str, str]:
        token = jwt.encode(
            {"sub": str(user_id)},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        return {"Authorization": f"Bearer {token}"}

    return make_auth_headers


@pytest.fixture
def ws_auth_headers(
    auth_headers: Callable[[uuid.UUID], dict[str, str]],
) -> Callable[[uuid.UUID], dict[str, str]]:
    return auth_headers
