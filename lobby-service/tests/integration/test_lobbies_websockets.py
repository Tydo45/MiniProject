import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from lobby.api_models import InviteResponse, LobbyResponse
from lobby.models import Invite, Lobby, OpenLobby
from lobby.routes.routes import ReadyResponse


def make_uuid(value: int) -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-0000-0000-{value:012d}")


def seed_and_commit(db_session: Session, *models: object) -> None:
    db_session.add_all(models)
    db_session.commit()


@pytest.mark.integration
def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.integration
@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/open-lobbies", None),
        ("GET", "/invites", None),
        ("POST", "/invites/send", {"invitee_id": str(make_uuid(2))}),
        ("POST", "/invites/accept", {"invite_id": str(make_uuid(3))}),
        ("POST", "/ready", {"lobby_id": str(make_uuid(4))}),
    ],
)
def test_protected_routes_require_bearer_auth(
    client: TestClient,
    method: str,
    path: str,
    payload: dict[str, str] | None,
) -> None:
    response = client.request(method, path, json=payload)

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.integration
def test_protected_routes_reject_malformed_token(client: TestClient) -> None:
    response = client.get(
        "/open-lobbies",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}


@pytest.mark.integration
def test_list_open_lobbies_returns_only_open_lobbies(
    client: TestClient,
    db_session: Session,
    auth_headers,
) -> None:
    user_id = make_uuid(10)
    open_lobby_1 = OpenLobby(
        id=make_uuid(101),
        host_player_id=make_uuid(11),
        is_open=True,
    )
    open_lobby_2 = OpenLobby(
        id=make_uuid(102),
        host_player_id=make_uuid(12),
        is_open=True,
    )
    closed_lobby = OpenLobby(
        id=make_uuid(103),
        host_player_id=make_uuid(13),
        is_open=False,
    )
    seed_and_commit(db_session, open_lobby_1, open_lobby_2, closed_lobby)

    response = client.get("/open-lobbies", headers=auth_headers(user_id))

    assert response.status_code == 200
    assert {(item["id"], item["host_player_id"], item["is_open"]) for item in response.json()} == {
        (str(open_lobby_1.id), str(open_lobby_1.host_player_id), True),
        (str(open_lobby_2.id), str(open_lobby_2.host_player_id), True),
    }


@pytest.mark.integration
def test_list_open_invites_returns_only_open_invites_for_current_user(
    client: TestClient,
    db_session: Session,
    auth_headers,
) -> None:
    current_user_id = make_uuid(20)
    matching_open_invite = Invite(
        id=make_uuid(201),
        from_player_id=make_uuid(21),
        to_player_id=current_user_id,
        is_open=True,
    )
    matching_closed_invite = Invite(
        id=make_uuid(202),
        from_player_id=make_uuid(22),
        to_player_id=current_user_id,
        is_open=False,
    )
    other_user_invite = Invite(
        id=make_uuid(203),
        from_player_id=make_uuid(23),
        to_player_id=make_uuid(24),
        is_open=True,
    )
    seed_and_commit(db_session, matching_open_invite, matching_closed_invite, other_user_invite)

    response = client.get("/invites", headers=auth_headers(current_user_id))

    assert response.status_code == 200
    assert len(response.json()) == 1

    invite = response.json()[0]
    assert invite["id"] == str(matching_open_invite.id)
    assert invite["from_player_id"] == str(matching_open_invite.from_player_id)
    assert invite["to_player_id"] == str(matching_open_invite.to_player_id)
    assert invite["is_open"] is True
    assert invite["responded_at"] is None
    created_at = datetime.fromisoformat(invite["created_at"].replace("Z", "+00:00"))
    assert created_at == matching_open_invite.created_at


@pytest.mark.integration
def test_send_invite_creates_invite_and_notifies_invitee(
    client: TestClient,
    db_session: Session,
    fake_notifier,
    auth_headers,
) -> None:
    sender_id = make_uuid(30)
    invitee_id = make_uuid(31)

    response = client.post(
        "/invites/send",
        json={"invitee_id": str(invitee_id)},
        headers=auth_headers(sender_id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["from_player_id"] == str(sender_id)
    assert body["to_player_id"] == str(invitee_id)
    assert body["is_open"] is True
    assert body["responded_at"] is None

    invite = db_session.execute(
        select(Invite).where(
            Invite.from_player_id == sender_id,
            Invite.to_player_id == invitee_id,
        )
    ).scalar_one()
    assert str(invite.id) == body["id"]
    assert invite.is_open is True

    assert len(fake_notifier.calls) == 1
    recipient_id, message = fake_notifier.calls[0]
    assert recipient_id == invitee_id
    assert message["type"] == "invite_created"
    inviteReponse = InviteResponse.model_validate(message["invite"])
    assert inviteReponse.id == invite.id
    assert inviteReponse.from_player_id == sender_id
    assert inviteReponse.to_player_id == invitee_id


@pytest.mark.integration
def test_send_invite_rejects_self_invite(
    client: TestClient,
    db_session: Session,
    fake_notifier,
    auth_headers,
) -> None:
    user_id = make_uuid(40)

    response = client.post(
        "/invites/send",
        json={"invitee_id": str(user_id)},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot invite yourself"}
    assert db_session.execute(select(Invite)).scalars().all() == []
    assert fake_notifier.calls == []


@pytest.mark.integration
def test_send_invite_rejects_duplicate_open_invite(
    client: TestClient,
    db_session: Session,
    fake_notifier,
    auth_headers,
) -> None:
    sender_id = make_uuid(50)
    invitee_id = make_uuid(51)
    existing_invite = Invite(
        id=make_uuid(501),
        from_player_id=sender_id,
        to_player_id=invitee_id,
        is_open=True,
    )
    seed_and_commit(db_session, existing_invite)

    response = client.post(
        "/invites/send",
        json={"invitee_id": str(invitee_id)},
        headers=auth_headers(sender_id),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Open invite already exists"}
    invites = db_session.execute(select(Invite)).scalars().all()
    assert [invite.id for invite in invites] == [existing_invite.id]
    assert fake_notifier.calls == []


@pytest.mark.integration
def test_send_invite_allows_resend_after_closed_invite(
    client: TestClient,
    db_session: Session,
    fake_notifier,
    auth_headers,
) -> None:
    sender_id = make_uuid(60)
    invitee_id = make_uuid(61)
    closed_invite = Invite(
        id=make_uuid(601),
        from_player_id=sender_id,
        to_player_id=invitee_id,
        is_open=False,
    )
    seed_and_commit(db_session, closed_invite)

    response = client.post(
        "/invites/send",
        json={"invitee_id": str(invitee_id)},
        headers=auth_headers(sender_id),
    )

    assert response.status_code == 200
    invites = (
        db_session.execute(
            select(Invite).where(
                Invite.from_player_id == sender_id,
                Invite.to_player_id == invitee_id,
            )
        )
        .scalars()
        .all()
    )
    assert len(invites) == 2
    assert sorted(invite.is_open for invite in invites) == [False, True]
    assert len(fake_notifier.calls) == 1
    assert fake_notifier.calls[0][0] == invitee_id


@pytest.mark.integration
def test_accept_invite_rejects_missing_invite(
    client: TestClient,
    db_session: Session,
    fake_notifier,
    auth_headers,
) -> None:
    user_id = make_uuid(70)

    response = client.post(
        "/invites/accept",
        json={"invite_id": str(make_uuid(701))},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invite doesn't exist"}
    assert db_session.execute(select(Lobby)).scalars().all() == []
    assert fake_notifier.calls == []


@pytest.mark.integration
def test_accept_invite_rejects_wrong_recipient(
    client: TestClient,
    db_session: Session,
    fake_notifier,
    auth_headers,
) -> None:
    authenticated_user_id = make_uuid(80)
    invite = Invite(
        id=make_uuid(801),
        from_player_id=make_uuid(81),
        to_player_id=make_uuid(82),
        is_open=True,
    )
    seed_and_commit(db_session, invite)

    response = client.post(
        "/invites/accept",
        json={"invite_id": str(invite.id)},
        headers=auth_headers(authenticated_user_id),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "User not authorized to accept invite"}

    refreshed_invite = db_session.execute(select(Invite).where(Invite.id == invite.id)).scalar_one()
    assert refreshed_invite.is_open is True
    assert refreshed_invite.responded_at is None
    assert db_session.execute(select(Lobby)).scalars().all() == []
    assert fake_notifier.calls == []


@pytest.mark.integration
def test_accept_invite_closes_invite_creates_lobby_and_notifies_inviter(
    client: TestClient,
    db_session: Session,
    fake_notifier,
    auth_headers,
) -> None:
    inviter_id = make_uuid(90)
    recipient_id = make_uuid(91)
    invite = Invite(
        id=make_uuid(901),
        from_player_id=inviter_id,
        to_player_id=recipient_id,
        is_open=True,
    )
    seed_and_commit(db_session, invite)

    response = client.post(
        "/invites/accept",
        json={"invite_id": str(invite.id)},
        headers=auth_headers(recipient_id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["player_id_1"] == str(inviter_id)
    assert body["player_id_2"] == str(recipient_id)
    assert body["player_1_ready"] is False
    assert body["player_2_ready"] is False

    refreshed_invite = db_session.execute(select(Invite).where(Invite.id == invite.id)).scalar_one()
    assert refreshed_invite.is_open is False
    assert refreshed_invite.responded_at is not None

    lobby = db_session.execute(select(Lobby).where(Lobby.id == uuid.UUID(body["id"]))).scalar_one()
    assert lobby.player_id_1 == inviter_id
    assert lobby.player_id_2 == recipient_id

    assert len(fake_notifier.calls) == 1
    recipient, message = fake_notifier.calls[0]
    assert recipient == inviter_id
    assert message["type"] == "invite_accepted"
    lobbyResponse = LobbyResponse.model_validate(message["lobby"])
    assert lobbyResponse.id == lobby.id
    assert lobbyResponse.player_id_1 == inviter_id
    assert lobbyResponse.player_id_2 == recipient_id


@pytest.mark.integration
@pytest.mark.parametrize(
    ("lobby", "user_id"),
    [
        (None, make_uuid(100)),
        (
            Lobby(
                id=make_uuid(1002),
                player_id_1=make_uuid(101),
                player_id_2=make_uuid(102),
            ),
            make_uuid(103),
        ),
    ],
)
def test_ready_rejects_when_user_has_no_accessible_lobby(
    client: TestClient,
    db_session: Session,
    fake_notifier,
    auth_headers,
    lobby: Lobby | None,
    user_id: uuid.UUID,
) -> None:
    lobby_id = make_uuid(1001) if lobby is None else lobby.id
    if lobby is not None:
        seed_and_commit(db_session, lobby)

    response = client.post(
        "/ready",
        json={"lobby_id": str(lobby_id)},
        headers=auth_headers(user_id),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "No Lobby to Ready for"}
    assert fake_notifier.calls == []


@pytest.mark.integration
def test_ready_marks_player_one_ready_without_notifying_when_other_not_ready(
    client: TestClient,
    db_session: Session,
    fake_notifier,
    auth_headers,
) -> None:
    lobby = Lobby(
        id=make_uuid(1101),
        player_id_1=make_uuid(111),
        player_id_2=make_uuid(112),
        player_1_ready=False,
        player_2_ready=False,
    )
    seed_and_commit(db_session, lobby)

    response = client.post(
        "/ready",
        json={"lobby_id": str(lobby.id)},
        headers=auth_headers(lobby.player_id_1),
    )

    assert response.status_code == 200
    assert response.json() == {"game_id": None, "both_ready": False}

    refreshed_lobby = db_session.execute(select(Lobby).where(Lobby.id == lobby.id)).scalar_one()
    assert refreshed_lobby.player_1_ready is True
    assert refreshed_lobby.player_2_ready is False
    assert fake_notifier.calls == []


@pytest.mark.integration
def test_ready_marks_player_two_ready_without_notifying_when_other_not_ready(
    client: TestClient,
    db_session: Session,
    fake_notifier,
    auth_headers,
) -> None:
    lobby = Lobby(
        id=make_uuid(1201),
        player_id_1=make_uuid(121),
        player_id_2=make_uuid(122),
        player_1_ready=False,
        player_2_ready=False,
    )
    seed_and_commit(db_session, lobby)

    response = client.post(
        "/ready",
        json={"lobby_id": str(lobby.id)},
        headers=auth_headers(lobby.player_id_2),
    )

    assert response.status_code == 200
    assert response.json() == {"game_id": None, "both_ready": False}

    refreshed_lobby = db_session.execute(select(Lobby).where(Lobby.id == lobby.id)).scalar_one()
    assert refreshed_lobby.player_1_ready is False
    assert refreshed_lobby.player_2_ready is True
    assert fake_notifier.calls == []


@pytest.mark.integration
def test_ready_notifies_opponent_when_both_players_are_ready(
    client: TestClient,
    db_session: Session,
    fake_notifier,
    auth_headers,
) -> None:
    lobby = Lobby(
        id=make_uuid(1301),
        player_id_1=make_uuid(131),
        player_id_2=make_uuid(132),
        player_1_ready=True,
        player_2_ready=False,
    )
    seed_and_commit(db_session, lobby)

    response = client.post(
        "/ready",
        json={"lobby_id": str(lobby.id)},
        headers=auth_headers(lobby.player_id_2),
    )

    assert response.status_code == 200
    assert response.json() == {"game_id": None, "both_ready": True}

    refreshed_lobby = db_session.execute(select(Lobby).where(Lobby.id == lobby.id)).scalar_one()
    assert refreshed_lobby.player_1_ready is True
    assert refreshed_lobby.player_2_ready is True

    assert len(fake_notifier.calls) == 1
    recipient, message = fake_notifier.calls[0]
    assert recipient == lobby.player_id_1
    assert message["type"] == "user_ready"
    readyResponse = ReadyResponse.model_validate(message["ReadyResponse"])
    assert readyResponse.both_ready is True
    assert readyResponse.game_id is None
