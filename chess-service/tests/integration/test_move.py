import uuid

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from chess_service.config import get_settings
from chess_service.db import SessionLocal
from chess_service.main import app
from chess_service.models import Game, GameEvent

pytestmark = pytest.mark.integration


@pytest.fixture
def client(postgres_container: str) -> TestClient:  # type: ignore
    del postgres_container
    with TestClient(app) as test_client:
        yield test_client


def make_auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    settings = get_settings()
    token = jwt.encode(
        {"sub": str(user_id)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


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


def get_game_events(game_id: uuid.UUID) -> list[GameEvent]:
    with SessionLocal() as session:
        stmt = select(GameEvent).where(GameEvent.game_id == game_id).order_by(GameEvent.ply)
        return list(session.scalars(stmt))


def test_move_creates_first_event_for_white(client: TestClient) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)

    response = client.post(
        f"/games/{game.id}/move",
        json={"uci": "e2e4"},
        headers=make_auth_headers(white_player_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["game_id"] == str(game.id)
    assert payload["ply"] == 1
    assert payload["uci_move"] == "e2e4"

    events = get_game_events(game.id)
    assert len(events) == 1
    assert events[0].ply == 1
    assert events[0].uci_move == "e2e4"


def test_move_creates_second_event_for_black(client: TestClient) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)
    add_event(game.id, 1, "e2e4")

    response = client.post(
        f"/games/{game.id}/move",
        json={"uci": "e7e5"},
        headers=make_auth_headers(black_player_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["game_id"] == str(game.id)
    assert payload["ply"] == 2
    assert payload["uci_move"] == "e7e5"

    events = get_game_events(game.id)
    assert [event.ply for event in events] == [1, 2]
    assert [event.uci_move for event in events] == ["e2e4", "e7e5"]


def test_move_rejects_illegal_move_for_position(client: TestClient) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)

    response = client.post(
        f"/games/{game.id}/move",
        json={"uci": "e2e5"},
        headers=make_auth_headers(white_player_id),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Illegal Move"}
    assert get_game_events(game.id) == []


def test_move_rejects_unknown_game_id(client: TestClient) -> None:
    response = client.post(
        f"/games/{uuid.uuid4()}/move",
        json={"uci": "e2e4"},
        headers=make_auth_headers(uuid.uuid4()),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Game Id"}


def test_move_rejects_non_player(client: TestClient) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    outsider_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)

    response = client.post(
        f"/games/{game.id}/move",
        json={"uci": "e2e4"},
        headers=make_auth_headers(outsider_id),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Not Allowed"}
    assert get_game_events(game.id) == []


def test_move_rejects_wrong_turn(client: TestClient) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)

    response = client.post(
        f"/games/{game.id}/move",
        json={"uci": "e7e5"},
        headers=make_auth_headers(black_player_id),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "User is not next to move"}
    assert get_game_events(game.id) == []


def test_move_rejects_invalid_token(client: TestClient) -> None:
    response = client.post(
        f"/games/{uuid.uuid4()}/move",
        json={"uci": "e2e4"},
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}


def test_move_requires_auth(client: TestClient) -> None:
    response = client.post(
        f"/games/{uuid.uuid4()}/move",
        json={"uci": "e2e4"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_move_rejects_missing_uci_field(client: TestClient) -> None:
    response = client.post(
        f"/games/{uuid.uuid4()}/move",
        json={},
        headers=make_auth_headers(uuid.uuid4()),
    )

    assert response.status_code == 400


def test_move_rejects_malformed_uci_string(client: TestClient) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)

    response = client.post(
        f"/games/{game.id}/move",
        json={"uci": "bad"},
        headers=make_auth_headers(white_player_id),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid UCI"}
    assert get_game_events(game.id) == []
