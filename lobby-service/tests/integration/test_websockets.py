import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.testclient import WebSocketDenialResponse

from lobby.models import Invite, Lobby
from lobby.realtime import manager


def make_uuid(value: int) -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-0000-0000-{value:012d}")


def seed_and_commit(db_session: Session, *models: object) -> None:
    db_session.add_all(models)
    db_session.commit()


@pytest.mark.integration
def test_websocket_rejects_missing_auth(websocket_client: TestClient) -> None:
    with pytest.raises(WebSocketDenialResponse) as exc_info:
        with websocket_client.websocket_connect("/ws"):
            pass

    assert exc_info.value.status_code == 401
    assert exc_info.value.json() == {"detail": "Not authenticated"}


@pytest.mark.integration
def test_websocket_rejects_invalid_token(websocket_client: TestClient) -> None:
    with pytest.raises(WebSocketDenialResponse) as exc_info:
        with websocket_client.websocket_connect(
            "/ws",
            headers={"Authorization": "Bearer not-a-real-token"},
        ):
            pass

    assert exc_info.value.status_code == 401
    assert exc_info.value.json() == {"detail": "Invalid token"}


@pytest.mark.integration
def test_websocket_accepts_valid_token_and_replies_to_ping(
    websocket_client: TestClient,
    ws_auth_headers,
) -> None:
    user_id = make_uuid(1)

    with websocket_client.websocket_connect("/ws", headers=ws_auth_headers(user_id)) as websocket:
        websocket.send_text("ping")

        assert websocket.receive_json() == {"type": "pong"}


@pytest.mark.integration
def test_websocket_disconnect_removes_user_from_manager(
    websocket_client: TestClient,
    ws_auth_headers,
) -> None:
    user_id = make_uuid(2)

    with websocket_client.websocket_connect("/ws", headers=ws_auth_headers(user_id)):
        assert manager.has_user(user_id) is True

    assert manager.has_user(user_id) is False


@pytest.mark.integration
def test_invite_send_delivers_event_to_connected_user(
    websocket_client: TestClient,
    ws_auth_headers,
) -> None:
    sender_id = make_uuid(10)
    invitee_id = make_uuid(11)

    with websocket_client.websocket_connect(
        "/ws",
        headers=ws_auth_headers(invitee_id),
    ) as websocket:
        response = websocket_client.post(
            "/invites/send",
            json={"invitee_id": str(invitee_id)},
            headers=ws_auth_headers(sender_id),
        )

        assert response.status_code == 200

        message = websocket.receive_json()
        assert message["type"] == "invite_created"
        assert message["invite"]["id"] == response.json()["id"]
        assert message["invite"]["from_player_id"] == str(sender_id)
        assert message["invite"]["to_player_id"] == str(invitee_id)
        assert message["invite"]["is_open"] is True


@pytest.mark.integration
def test_invite_accept_delivers_event_to_connected_inviter(
    websocket_client: TestClient,
    db_session: Session,
    ws_auth_headers,
) -> None:
    inviter_id = make_uuid(20)
    recipient_id = make_uuid(21)
    invite = Invite(
        id=make_uuid(2001),
        from_player_id=inviter_id,
        to_player_id=recipient_id,
        is_open=True,
    )
    seed_and_commit(db_session, invite)

    with websocket_client.websocket_connect(
        "/ws",
        headers=ws_auth_headers(inviter_id),
    ) as websocket:
        response = websocket_client.post(
            "/invites/accept",
            json={"invite_id": str(invite.id)},
            headers=ws_auth_headers(recipient_id),
        )

        assert response.status_code == 200

        message = websocket.receive_json()
        assert message["type"] == "invite_accepted"
        assert message["lobby"]["id"] == response.json()["id"]
        assert message["lobby"]["player_id_1"] == str(inviter_id)
        assert message["lobby"]["player_id_2"] == str(recipient_id)
        assert message["lobby"]["player_1_ready"] is False
        assert message["lobby"]["player_2_ready"] is False


@pytest.mark.integration
def test_ready_delivers_event_to_connected_opponent(
    websocket_client: TestClient,
    db_session: Session,
    ws_auth_headers,
) -> None:
    player_1_id = make_uuid(30)
    player_2_id = make_uuid(31)
    lobby = Lobby(
        id=make_uuid(3001),
        player_id_1=player_1_id,
        player_id_2=player_2_id,
        player_1_ready=True,
        player_2_ready=False,
    )
    seed_and_commit(db_session, lobby)

    with websocket_client.websocket_connect(
        "/ws",
        headers=ws_auth_headers(player_1_id),
    ) as websocket:
        response = websocket_client.post(
            "/ready",
            json={"lobby_id": str(lobby.id)},
            headers=ws_auth_headers(player_2_id),
        )

        assert response.status_code == 200
        assert response.json() == {"game_id": None, "both_ready": True}

        message = websocket.receive_json()
        assert message == {
            "type": "user_ready",
            "ReadyResponse": {
                "game_id": None,
                "both_ready": True,
            },
        }


@pytest.mark.integration
def test_multiple_websockets_for_same_user_each_receive_event(
    websocket_client: TestClient,
    ws_auth_headers,
) -> None:
    sender_id = make_uuid(40)
    recipient_id = make_uuid(41)

    with websocket_client.websocket_connect(
        "/ws",
        headers=ws_auth_headers(recipient_id),
    ) as websocket_1:
        with websocket_client.websocket_connect(
            "/ws",
            headers=ws_auth_headers(recipient_id),
        ) as websocket_2:
            response = websocket_client.post(
                "/invites/send",
                json={"invitee_id": str(recipient_id)},
                headers=ws_auth_headers(sender_id),
            )

            assert response.status_code == 200

            message_1 = websocket_1.receive_json()
            message_2 = websocket_2.receive_json()

            assert message_1["type"] == "invite_created"
            assert message_2["type"] == "invite_created"
            assert message_1["invite"]["id"] == response.json()["id"]
            assert message_2["invite"]["id"] == response.json()["id"]


@pytest.mark.integration
def test_invite_send_succeeds_without_connected_websocket(
    websocket_client: TestClient,
    ws_auth_headers,
) -> None:
    sender_id = make_uuid(50)
    recipient_id = make_uuid(51)

    response = websocket_client.post(
        "/invites/send",
        json={"invitee_id": str(recipient_id)},
        headers=ws_auth_headers(sender_id),
    )

    assert response.status_code == 200
    assert manager.has_user(recipient_id) is False
