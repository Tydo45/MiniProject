import uuid
from datetime import datetime

import pytest
from conftest import add_event, get_game, make_auth_headers, make_service_auth_headers
from fastapi.testclient import TestClient

from chess_service.db import SessionLocal
from chess_service.models import Game

pytestmark = pytest.mark.integration


def assert_iso_datetime(value: str) -> None:
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def set_game_outcome(
    game_id: uuid.UUID,
    *,
    winner_player_id: uuid.UUID | None = None,
    is_draw: bool = False,
) -> None:
    with SessionLocal() as session:
        game = session.get(Game, game_id)
        assert game is not None
        game.winner_player_id = winner_player_id
        game.is_draw = is_draw
        session.commit()


def test_games_requires_auth(client: TestClient) -> None:
    response = client.post("/games")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_games_rejects_invalid_token(client: TestClient) -> None:
    response = client.post(
        "/games",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}


def test_games_returns_empty_list_when_user_has_no_games(
    client: TestClient,
) -> None:
    response = client.post(
        "/games",
        headers=make_auth_headers(uuid.uuid4()),
    )

    assert response.status_code == 200
    assert response.json() == {"games": []}


def test_games_returns_only_open_games_for_authenticated_player(
    client: TestClient,
    create_game,
) -> None:
    user_id = uuid.uuid4()
    opponent_id = uuid.uuid4()

    open_as_white = create_game(user_id, opponent_id)
    add_event(open_as_white.id, 1, "e2e4")

    open_as_black = create_game(opponent_id, user_id)
    add_event(open_as_black.id, 1, "d2d4")
    add_event(open_as_black.id, 2, "d7d5")

    finished_game = create_game(user_id, uuid.uuid4())
    set_game_outcome(finished_game.id, winner_player_id=user_id)

    drawn_game = create_game(user_id, uuid.uuid4())
    set_game_outcome(drawn_game.id, is_draw=True)

    other_game = create_game(uuid.uuid4(), uuid.uuid4())

    response = client.post(
        "/games",
        headers=make_auth_headers(user_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert sorted(game["id"] for game in payload["games"]) == sorted(
        [str(open_as_white.id), str(open_as_black.id)]
    )

    games_by_id = {game["id"]: game for game in payload["games"]}
    assert str(finished_game.id) not in games_by_id
    assert str(drawn_game.id) not in games_by_id
    assert str(other_game.id) not in games_by_id

    white_game = games_by_id[str(open_as_white.id)]
    assert white_game["white_player_id"] == str(user_id)
    assert white_game["black_player_id"] == str(opponent_id)
    assert white_game["winner_player_id"] is None
    assert white_game["is_draw"] is False
    assert_iso_datetime(white_game["created_at"])
    assert [event["uci_move"] for event in white_game["events"]] == ["e2e4"]
    assert [event["ply"] for event in white_game["events"]] == [1]
    assert_iso_datetime(white_game["events"][0]["created_at"])

    black_game = games_by_id[str(open_as_black.id)]
    assert black_game["white_player_id"] == str(opponent_id)
    assert black_game["black_player_id"] == str(user_id)
    assert black_game["winner_player_id"] is None
    assert black_game["is_draw"] is False
    assert_iso_datetime(black_game["created_at"])
    assert [event["uci_move"] for event in black_game["events"]] == ["d2d4", "d7d5"]
    assert [event["ply"] for event in black_game["events"]] == [1, 2]


def test_create_game_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/games/create",
        json={
            "white_player_id": str(uuid.uuid4()),
            "black_player_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_create_game_rejects_invalid_token(client: TestClient) -> None:
    response = client.post(
        "/games/create",
        json={
            "white_player_id": str(uuid.uuid4()),
            "black_player_id": str(uuid.uuid4()),
        },
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}


def test_create_game_persists_and_returns_created_game(
    client: TestClient,
) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()

    response = client.post(
        "/games/create",
        json={
            "white_player_id": str(white_player_id),
            "black_player_id": str(black_player_id),
        },
        headers=make_service_auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["white_player_id"] == str(white_player_id)
    assert payload["black_player_id"] == str(black_player_id)
    assert payload["winner_player_id"] is None
    assert payload["is_draw"] is False
    assert payload["events"] == []
    assert_iso_datetime(payload["created_at"])

    persisted_game = get_game(uuid.UUID(payload["id"]))
    assert persisted_game.white_player_id == white_player_id
    assert persisted_game.black_player_id == black_player_id
    assert persisted_game.winner_player_id is None
    assert persisted_game.is_draw is False


def test_create_game_rejects_user_token(
    client: TestClient,
) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    requester_id = uuid.uuid4()

    response = client.post(
        "/games/create",
        json={
            "white_player_id": str(white_player_id),
            "black_player_id": str(black_player_id),
        },
        headers=make_auth_headers(requester_id),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Service token required"}


def test_create_game_allows_service_token_when_requester_is_not_a_player(
    client: TestClient,
) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()

    response = client.post(
        "/games/create",
        json={
            "white_player_id": str(white_player_id),
            "black_player_id": str(black_player_id),
        },
        headers=make_service_auth_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["white_player_id"] == str(white_player_id)
    assert payload["black_player_id"] == str(black_player_id)

    persisted_game = get_game(uuid.UUID(payload["id"]))
    assert persisted_game.white_player_id == white_player_id
    assert persisted_game.black_player_id == black_player_id


@pytest.mark.parametrize(
    "body",
    [
        {"white_player_id": str(uuid.uuid4())},
        {"black_player_id": str(uuid.uuid4())},
        {
            "white_player_id": "not-a-uuid",
            "black_player_id": str(uuid.uuid4()),
        },
        {
            "white_player_id": str(uuid.uuid4()),
            "black_player_id": "not-a-uuid",
        },
    ],
)
def test_create_game_rejects_malformed_bodies(
    client: TestClient,
    body: dict[str, str],
) -> None:
    response = client.post(
        "/games/create",
        json=body,
        headers=make_service_auth_headers(),
    )

    assert response.status_code == 422
