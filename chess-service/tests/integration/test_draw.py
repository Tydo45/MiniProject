import uuid

import pytest
from conftest import add_event, get_game, make_auth_headers
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def assert_game_draw_state(
    game_id: uuid.UUID,
    *,
    draw_offered_by: uuid.UUID | None,
    is_draw: bool,
) -> None:
    game = get_game(game_id)
    assert game.draw_offered_by == draw_offered_by
    assert game.is_draw is is_draw


@pytest.mark.parametrize("path_suffix", ["draw", "draw/accept", "draw/decline"])
def test_draw_endpoints_require_auth(client: TestClient, path_suffix: str) -> None:
    response = client.post(f"/games/{uuid.uuid4()}/{path_suffix}")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.parametrize("path_suffix", ["draw", "draw/accept", "draw/decline"])
def test_draw_endpoints_reject_invalid_token(
    client: TestClient,
    path_suffix: str,
) -> None:
    response = client.post(
        f"/games/{uuid.uuid4()}/{path_suffix}",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}


@pytest.mark.parametrize("path_suffix", ["draw", "draw/accept", "draw/decline"])
def test_draw_endpoints_reject_unknown_game_id(
    client: TestClient,
    path_suffix: str,
) -> None:
    response = client.post(
        f"/games/{uuid.uuid4()}/{path_suffix}",
        headers=make_auth_headers(uuid.uuid4()),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Game Id"}


@pytest.mark.parametrize("path_suffix", ["draw", "draw/accept", "draw/decline"])
def test_draw_endpoints_reject_non_player(
    client: TestClient,
    path_suffix: str,
    create_game,
) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    outsider_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)

    response = client.post(
        f"/games/{game.id}/{path_suffix}",
        headers=make_auth_headers(outsider_id),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Not Allowed"}
    assert_game_draw_state(game.id, draw_offered_by=None, is_draw=False)


def test_draw_rejects_wrong_turn(client: TestClient, create_game) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)

    response = client.post(
        f"/games/{game.id}/draw",
        headers=make_auth_headers(black_player_id),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "User is not next to move"}
    assert_game_draw_state(game.id, draw_offered_by=None, is_draw=False)


def test_draw_allows_white_to_offer_on_initial_position(client: TestClient, create_game) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)

    response = client.post(
        f"/games/{game.id}/draw",
        headers=make_auth_headers(white_player_id),
    )

    assert response.status_code == 200
    assert response.json() is None
    assert_game_draw_state(game.id, draw_offered_by=white_player_id, is_draw=False)


def test_draw_allows_black_to_offer_after_white_moves(client: TestClient, create_game) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)
    add_event(game.id, 1, "e2e4")

    response = client.post(
        f"/games/{game.id}/draw",
        headers=make_auth_headers(black_player_id),
    )

    assert response.status_code == 200
    assert response.json() is None
    assert_game_draw_state(game.id, draw_offered_by=black_player_id, is_draw=False)


def test_draw_rejects_second_offer_while_one_is_pending(client: TestClient, create_game) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)

    first_response = client.post(
        f"/games/{game.id}/draw",
        headers=make_auth_headers(white_player_id),
    )
    assert first_response.status_code == 200

    response = client.post(
        f"/games/{game.id}/draw",
        headers=make_auth_headers(white_player_id),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Draw offer awaiting response"}
    assert_game_draw_state(game.id, draw_offered_by=white_player_id, is_draw=False)


def test_draw_without_connected_sockets_still_succeeds(client: TestClient, create_game) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)

    response = client.post(
        f"/games/{game.id}/draw",
        headers=make_auth_headers(white_player_id),
    )

    assert response.status_code == 200
    assert_game_draw_state(game.id, draw_offered_by=white_player_id, is_draw=False)


def test_draw_notifies_only_the_opponent_over_websocket(client: TestClient, create_game) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)
    expected_message = {"type": "draw_proposed", "gameId": str(game.id)}

    with client.websocket_connect("/ws", headers=make_auth_headers(white_player_id)) as white_ws:
        with client.websocket_connect(
            "/ws",
            headers=make_auth_headers(black_player_id),
        ) as black_ws:
            response = client.post(
                f"/games/{game.id}/draw",
                headers=make_auth_headers(white_player_id),
            )

            assert response.status_code == 200
            assert black_ws.receive_json() == expected_message
            white_ws.send_text("ping")
            assert white_ws.receive_json() == {"type": "pong"}


def test_draw_notifies_all_open_sockets_for_the_opponent(client: TestClient, create_game) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)
    expected_message = {"type": "draw_proposed", "gameId": str(game.id)}

    with client.websocket_connect(
        "/ws", headers=make_auth_headers(black_player_id)
    ) as black_ws_one:
        with client.websocket_connect(
            "/ws",
            headers=make_auth_headers(black_player_id),
        ) as black_ws_two:
            response = client.post(
                f"/games/{game.id}/draw",
                headers=make_auth_headers(white_player_id),
            )

            assert response.status_code == 200
            assert black_ws_one.receive_json() == expected_message
            assert black_ws_two.receive_json() == expected_message


def test_accept_draw_marks_game_drawn_and_clears_offer(client: TestClient, create_game) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)
    client.post(
        f"/games/{game.id}/draw",
        headers=make_auth_headers(white_player_id),
    )

    response = client.post(
        f"/games/{game.id}/draw/accept",
        headers=make_auth_headers(black_player_id),
    )

    assert response.status_code == 200
    assert response.json() is None
    assert_game_draw_state(game.id, draw_offered_by=None, is_draw=True)


def test_accept_draw_rejects_when_no_offer_is_pending(client: TestClient, create_game) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)

    response = client.post(
        f"/games/{game.id}/draw/accept",
        headers=make_auth_headers(black_player_id),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Draw not Offered by Opponent"}
    assert_game_draw_state(game.id, draw_offered_by=None, is_draw=False)


def test_accept_draw_rejects_the_player_who_made_the_offer(client: TestClient, create_game) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)
    client.post(
        f"/games/{game.id}/draw",
        headers=make_auth_headers(white_player_id),
    )

    response = client.post(
        f"/games/{game.id}/draw/accept",
        headers=make_auth_headers(white_player_id),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Draw not Offered by Opponent"}
    assert_game_draw_state(game.id, draw_offered_by=white_player_id, is_draw=False)


def test_accept_draw_notifies_the_original_offerer(client: TestClient, create_game) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)
    expected_message = {"type": "draw_accepted", "gameId": str(game.id)}

    client.post(
        f"/games/{game.id}/draw",
        headers=make_auth_headers(white_player_id),
    )

    with client.websocket_connect("/ws", headers=make_auth_headers(white_player_id)) as white_ws:
        response = client.post(
            f"/games/{game.id}/draw/accept",
            headers=make_auth_headers(black_player_id),
        )

        assert response.status_code == 200
        assert white_ws.receive_json() == expected_message


def test_accept_draw_notifies_all_open_sockets_for_the_offerer(
    client: TestClient, create_game
) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)
    expected_message = {"type": "draw_accepted", "gameId": str(game.id)}

    client.post(
        f"/games/{game.id}/draw",
        headers=make_auth_headers(white_player_id),
    )

    with client.websocket_connect(
        "/ws", headers=make_auth_headers(white_player_id)
    ) as white_ws_one:
        with client.websocket_connect(
            "/ws", headers=make_auth_headers(white_player_id)
        ) as white_ws_two:
            response = client.post(
                f"/games/{game.id}/draw/accept",
                headers=make_auth_headers(black_player_id),
            )

            assert response.status_code == 200
            assert white_ws_one.receive_json() == expected_message
            assert white_ws_two.receive_json() == expected_message


def test_decline_draw_clears_offer_without_marking_game_drawn(
    client: TestClient, create_game
) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)
    client.post(
        f"/games/{game.id}/draw",
        headers=make_auth_headers(white_player_id),
    )

    response = client.post(
        f"/games/{game.id}/draw/decline",
        headers=make_auth_headers(black_player_id),
    )

    assert response.status_code == 200
    assert response.json() is None
    assert_game_draw_state(game.id, draw_offered_by=None, is_draw=False)


def test_decline_draw_rejects_when_no_offer_is_pending(client: TestClient, create_game) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)

    response = client.post(
        f"/games/{game.id}/draw/decline",
        headers=make_auth_headers(black_player_id),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Draw not Offered by Opponent"}
    assert_game_draw_state(game.id, draw_offered_by=None, is_draw=False)


def test_decline_draw_rejects_the_player_who_made_the_offer(
    client: TestClient, create_game
) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)
    client.post(
        f"/games/{game.id}/draw",
        headers=make_auth_headers(white_player_id),
    )

    response = client.post(
        f"/games/{game.id}/draw/decline",
        headers=make_auth_headers(white_player_id),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Draw not Offered by Opponent"}
    assert_game_draw_state(game.id, draw_offered_by=white_player_id, is_draw=False)


def test_decline_draw_notifies_the_original_offerer(client: TestClient, create_game) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)
    expected_message = {"type": "draw_declined", "gameId": str(game.id)}

    client.post(
        f"/games/{game.id}/draw",
        headers=make_auth_headers(white_player_id),
    )

    with client.websocket_connect("/ws", headers=make_auth_headers(white_player_id)) as white_ws:
        response = client.post(
            f"/games/{game.id}/draw/decline",
            headers=make_auth_headers(black_player_id),
        )

        assert response.status_code == 200
        assert white_ws.receive_json() == expected_message


def test_decline_draw_notifies_all_open_sockets_for_the_offerer(
    client: TestClient, create_game
) -> None:
    white_player_id = uuid.uuid4()
    black_player_id = uuid.uuid4()
    game = create_game(white_player_id, black_player_id)
    expected_message = {"type": "draw_declined", "gameId": str(game.id)}

    client.post(
        f"/games/{game.id}/draw",
        headers=make_auth_headers(white_player_id),
    )

    with client.websocket_connect(
        "/ws", headers=make_auth_headers(white_player_id)
    ) as white_ws_one:
        with client.websocket_connect(
            "/ws", headers=make_auth_headers(white_player_id)
        ) as white_ws_two:
            response = client.post(
                f"/games/{game.id}/draw/decline",
                headers=make_auth_headers(black_player_id),
            )

            assert response.status_code == 200
            assert white_ws_one.receive_json() == expected_message
            assert white_ws_two.receive_json() == expected_message
