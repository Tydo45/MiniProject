import os
import subprocess
import time
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from chess_service.config import (
    get_environment_database_url,
    get_settings,
    reset_settings_cache,
)
from chess_service.db import SessionLocal
from chess_service.main import app
from chess_service.models import Game, GameEvent
from chess_service.realtime import manager

reset_settings_cache()
database_url = get_environment_database_url()


@pytest.fixture(scope="session", autouse=False)
def postgres_container():
    postgres_container_name = f"chess-test-postgres-{uuid.uuid4().hex[:8]}"

    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            postgres_container_name,
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

    yield postgres_container_name

    subprocess.run(["docker", "rm", "-f", postgres_container_name], check=False)


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
def client(postgres_container: str) -> TestClient:  # type: ignore
    del postgres_container
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clear_realtime_connections() -> None:  # type: ignore
    manager._connections.clear()
    yield
    manager._connections.clear()


def make_token(payload: dict[str, str]) -> str:
    settings = get_settings()
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def make_auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token({'sub': str(user_id)})}"}


def create_game(
    white_player_id: uuid.UUID,
    black_player_id: uuid.UUID,
) -> Game:
    with SessionLocal() as session:
        game = Game(
            white_player_id=white_player_id,
            black_player_id=black_player_id,
        )
        session.add(game)
        session.commit()
        session.refresh(game)
        return game


def add_event(game_id: uuid.UUID, ply: int, uci_move: str) -> GameEvent:
    with SessionLocal() as session:
        event = GameEvent(
            game_id=game_id,
            ply=ply,
            uci_move=uci_move,
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        return event


def get_game(game_id: uuid.UUID) -> Game:
    with SessionLocal() as session:
        stmt = select(Game).where(Game.id == game_id)
        return session.execute(stmt).scalar_one()
