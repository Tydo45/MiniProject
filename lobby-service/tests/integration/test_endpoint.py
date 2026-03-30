import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from lobby.api_models import LobbyResponse
from lobby.models import Lobby, OpenLobby


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
def test_create_open_lobby_creates_open_lobby_for_authenticated_user(
    client: TestClient,
    db_session: Session,
    auth_headers,
) -> None:
    user_id = make_uuid(10)

    response = client.post("/open-lobbies", headers=auth_headers(user_id))

    assert response.status_code == 200
    body = response.json()
    assert body["host_player_id"] == str(user_id)
    assert body["is_open"] is True
    assert body["joined_at"] is None

    lobbies = (
        db_session.execute(select(OpenLobby).where(OpenLobby.host_player_id == user_id))
        .scalars()
        .all()
    )
    assert len(lobbies) == 1
    lobby = lobbies[0]
    assert str(lobby.id) == body["id"]
    assert lobby.host_player_id == user_id
    assert lobby.is_open is True
    assert lobby.joined_at is None


@pytest.mark.integration
def test_create_open_lobby_rejects_second_open_lobby_for_same_host(
    client: TestClient,
    db_session: Session,
    auth_headers,
) -> None:
    user_id = make_uuid(20)
    existing_lobby = OpenLobby(
        id=make_uuid(201),
        host_player_id=user_id,
        is_open=True,
    )
    seed_and_commit(db_session, existing_lobby)

    response = client.post("/open-lobbies", headers=auth_headers(user_id))

    assert response.status_code == 400
    assert response.json() == {"detail": "You already have an open lobby"}

    lobbies = (
        db_session.execute(select(OpenLobby).where(OpenLobby.host_player_id == user_id))
        .scalars()
        .all()
    )
    assert [lobby.id for lobby in lobbies] == [existing_lobby.id]


@pytest.mark.integration
def test_create_open_lobby_allows_creation_when_existing_lobby_is_closed(
    client: TestClient,
    db_session: Session,
    auth_headers,
) -> None:
    user_id = make_uuid(30)
    closed_lobby = OpenLobby(
        id=make_uuid(301),
        host_player_id=user_id,
        is_open=False,
    )
    seed_and_commit(db_session, closed_lobby)

    response = client.post("/open-lobbies", headers=auth_headers(user_id))

    assert response.status_code == 200

    lobbies = (
        db_session.execute(select(OpenLobby).where(OpenLobby.host_player_id == user_id))
        .scalars()
        .all()
    )
    assert len(lobbies) == 2
    assert sorted(lobby.is_open for lobby in lobbies) == [False, True]


@pytest.mark.integration
def test_join_open_lobby_rejects_missing_lobby(
    client: TestClient,
    db_session: Session,
    fake_notifier,
    auth_headers,
) -> None:
    user_id = make_uuid(40)
    lobby_id = make_uuid(401)

    response = client.get(
        f"/open-lobbies/join/{lobby_id}",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": f"Open Lobby: {lobby_id} not available"}
    assert db_session.execute(select(Lobby)).scalars().all() == []
    assert fake_notifier.calls == []


@pytest.mark.integration
def test_join_open_lobby_rejects_joining_own_lobby(
    client: TestClient,
    db_session: Session,
    fake_notifier,
    auth_headers,
) -> None:
    user_id = make_uuid(50)
    open_lobby = OpenLobby(
        id=make_uuid(501),
        host_player_id=user_id,
        is_open=True,
    )
    seed_and_commit(db_session, open_lobby)

    response = client.get(
        f"/open-lobbies/join/{open_lobby.id}",
        headers=auth_headers(user_id),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot join your own open lobby"}

    refreshed_open_lobby = db_session.execute(
        select(OpenLobby).where(OpenLobby.id == open_lobby.id)
    ).scalar_one()
    assert refreshed_open_lobby.is_open is True
    assert refreshed_open_lobby.joined_at is None
    assert db_session.execute(select(Lobby)).scalars().all() == []
    assert fake_notifier.calls == []


@pytest.mark.integration
def test_join_open_lobby_creates_lobby_closes_open_lobby_and_notifies_host(
    client: TestClient,
    db_session: Session,
    fake_notifier,
    auth_headers,
) -> None:
    host_user_id = make_uuid(60)
    joining_user_id = make_uuid(61)
    open_lobby = OpenLobby(
        id=make_uuid(601),
        host_player_id=host_user_id,
        is_open=True,
    )
    seed_and_commit(db_session, open_lobby)

    response = client.get(
        f"/open-lobbies/join/{open_lobby.id}",
        headers=auth_headers(joining_user_id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["player_id_1"] == str(host_user_id)
    assert body["player_id_2"] == str(joining_user_id)
    assert body["player_1_ready"] is False
    assert body["player_2_ready"] is False

    refreshed_open_lobby = db_session.execute(
        select(OpenLobby).where(OpenLobby.id == open_lobby.id)
    ).scalar_one()
    assert refreshed_open_lobby.is_open is False
    assert refreshed_open_lobby.joined_at is not None

    lobby = db_session.execute(select(Lobby).where(Lobby.id == uuid.UUID(body["id"]))).scalar_one()
    assert lobby.player_id_1 == host_user_id
    assert lobby.player_id_2 == joining_user_id

    assert len(fake_notifier.calls) == 1
    recipient, message = fake_notifier.calls[0]
    assert recipient == host_user_id
    assert message["type"] == "open_join"
    lobby_response = LobbyResponse.model_validate(message["lobby"])
    assert lobby_response.id == lobby.id
    assert lobby_response.player_id_1 == host_user_id
    assert lobby_response.player_id_2 == joining_user_id
