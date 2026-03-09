import os
import subprocess
import time

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth.config import get_environment_database_url, reset_settings_cache

load_dotenv()
reset_settings_cache()
database_url = get_environment_database_url()


@pytest.fixture(scope="session", autouse=True)
def postgres_container():
    subprocess.run(["docker", "rm", "-f", "auth-test-postgres"], check=False)
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "auth-test-postgres",
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

    subprocess.run(["docker", "rm", "-f", "auth-test-postgres"], check=False)


@pytest.fixture
def db_session():
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)

    connection = engine.connect()
    transaction = connection.begin()

    session = SessionLocal(bind=connection)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client():
    from auth.main import app

    with TestClient(app) as test_client:
        yield test_client
