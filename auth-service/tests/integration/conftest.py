import os
import subprocess
import time

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

database_url = os.getenv("DATABASE_URL")

if database_url is None:
    raise RuntimeError("DATABASE_URL is not set")


@pytest.fixture(scope="session", autouse=True)
def postgres_container():
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
            "POSTGRES_DB=auth_db",
            "-e",
            "POSTGRES_USER=auth_service",
            "-e",
            "POSTGRES_PASSWORD=auth_pass",
            "postgres:16",
        ],
        check=True,
    )

    time.sleep(5)

    subprocess.run(["alembic", "upgrade", "head"], check=True)

    yield

    subprocess.run(["docker", "rm", "-f", "auth-test-postgres"], check=False)


engine = create_engine(database_url)
SessionLocal = sessionmaker(bind=engine)


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()

    session = SessionLocal(bind=connection)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
