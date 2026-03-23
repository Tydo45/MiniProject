import uuid

import pytest
from conftest import add_event, create_game, make_auth_headers, make_token
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.testclient import WebSocketDenialResponse

from chess_service.db import SessionLocal
from chess_service.models import GameEvent
from chess_service.realtime import manager

pytestmark = pytest.mark.integration


def get_game_events(game_id: uuid.UUID) -> list[GameEvent]:
    with SessionLocal() as session:
        stmt = select(GameEvent).where(GameEvent.game_id == game_id).order_by(GameEvent.ply)
        return list(session.scalars(stmt))


def assert_websocket_denied(
    client: TestClient,
    headers: dict[str, str] | None,
    expected_status: int,
    expected_body: dict[str, str],
) -> None:
    with pytest.raises(WebSocketDenialResponse) as exc_info:
        with client.websocket_connect("/ws", headers=headers or {}):
            pass

    response = exc_info.value
    assert response.status_code == expected_status
    assert response.json() == expected_body


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


def test_websocket_connects_with_valid_token_and_disconnect_cleans_up(client: TestClient) -> None:
    user_id = uuid.uuid4()

    assert not manager.has_user(user_id)

    with client.websocket_connect("/ws", headers=make_auth_headers(user_id)):
        assert manager.has_user(user_id)

    assert not manager.has_user(user_id)


def test_websocket_ping_returns_pong(client: TestClient) -> None:
    user_id = uuid.uuid4()

    with client.websocket_connect("/ws", headers=make_auth_headers(user_id)) as websocket:
        websocket.send_text("ping")
        assert websocket.receive_json() == {"type": "pong"}


def test_websocket_rejects_missing_authorization_header(client: TestClient) -> None:
    assert_websocket_denied(
        client,
        headers=None,
        expected_status=401,
        expected_body={"detail": "Not authenticated"},
    )


def test_websocket_rejects_non_bearer_scheme(client: TestClient) -> None:
    assert_websocket_denied(
        client,
        headers={"Authorization": "Basic not-a-bearer-token"},
        expected_status=401,
        expected_body={"detail": "Not authenticated"},
    )


def test_websocket_rejects_invalid_token(client: TestClient) -> None:
    assert_websocket_denied(
        client,
        headers={"Authorization": "Bearer not-a-valid-token"},
        expected_status=401,
        expected_body={"detail": "Invalid token"},
    )


def test_websocket_rejects_token_with_invalid_subject(client: TestClient) -> None:
    invalid_subject_token = make_token({"sub": "not-a-uuid"})

    assert_websocket_denied(
        client,
        headers={"Authorization": f"Bearer {invalid_subject_token}"},
        expected_status=401,
        expected_body={"detail": "Token subject is not a valid UUID"},
    )


def test_move_notifies_both_connected_players_over_websocket(client: TestClient) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)
    expected_message = {"type": "game_updated", "gameId": str(game.id)}

    with client.websocket_connect("/ws", headers=make_auth_headers(white_player_id)) as white_ws:
        with client.websocket_connect(
            "/ws", headers=make_auth_headers(black_player_id)
        ) as black_ws:
            response = client.post(
                f"/games/{game.id}/move",
                json={"uci": "e2e4"},
                headers=make_auth_headers(white_player_id),
            )

            assert response.status_code == 200
            assert white_ws.receive_json() == expected_message
            assert black_ws.receive_json() == expected_message


def test_move_notifies_all_open_sockets_for_same_user(client: TestClient) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)
    expected_message = {"type": "game_updated", "gameId": str(game.id)}

    with client.websocket_connect(
        "/ws", headers=make_auth_headers(white_player_id)
    ) as white_ws_one:
        with client.websocket_connect(
            "/ws", headers=make_auth_headers(white_player_id)
        ) as white_ws_two:
            with client.websocket_connect(
                "/ws", headers=make_auth_headers(black_player_id)
            ) as black_ws:
                response = client.post(
                    f"/games/{game.id}/move",
                    json={"uci": "e2e4"},
                    headers=make_auth_headers(white_player_id),
                )

                assert response.status_code == 200
                assert white_ws_one.receive_json() == expected_message
                assert white_ws_two.receive_json() == expected_message
                assert black_ws.receive_json() == expected_message


def test_move_without_connected_sockets_still_succeeds(client: TestClient) -> None:
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
