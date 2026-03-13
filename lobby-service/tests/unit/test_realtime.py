import uuid
from unittest.mock import AsyncMock

import pytest

import lobby.realtime as realtime_module


@pytest.fixture
def manager():
    return realtime_module.ConnectionManager()


@pytest.fixture
def user_id():
    return uuid.uuid4()


def make_websocket():
    websocket = AsyncMock()
    websocket.accept = AsyncMock()
    websocket.send_json = AsyncMock()
    return websocket


@pytest.mark.unit
async def test_connect_accepts_websocket_and_tracks_connection(manager, user_id):
    websocket = make_websocket()

    await manager.connect(user_id, websocket)

    websocket.accept.assert_awaited_once()
    assert manager.has_user(user_id) is True
    assert websocket in manager._connections[user_id]


@pytest.mark.unit
async def test_connect_tracks_multiple_connections_for_same_user(manager, user_id):
    websocket1 = make_websocket()
    websocket2 = make_websocket()

    await manager.connect(user_id, websocket1)
    await manager.connect(user_id, websocket2)

    assert manager.has_user(user_id) is True
    assert websocket1 in manager._connections[user_id]
    assert websocket2 in manager._connections[user_id]
    assert len(manager._connections[user_id]) == 2


def test_disconnect_removes_existing_connection(manager, user_id):
    websocket = make_websocket()
    manager._connections[user_id].add(websocket)

    manager.disconnect(user_id, websocket)

    assert user_id not in manager._connections
    assert manager.has_user(user_id) is False


def test_disconnect_removes_only_one_of_multiple_connections(manager, user_id):
    websocket1 = make_websocket()
    websocket2 = make_websocket()
    manager._connections[user_id].add(websocket1)
    manager._connections[user_id].add(websocket2)

    manager.disconnect(user_id, websocket1)

    assert manager.has_user(user_id) is True
    assert websocket1 not in manager._connections[user_id]
    assert websocket2 in manager._connections[user_id]


def test_disconnect_does_nothing_if_user_not_present(manager, user_id):
    websocket = make_websocket()

    manager.disconnect(user_id, websocket)

    assert manager.has_user(user_id) is False


def test_disconnect_does_nothing_if_websocket_not_present_for_existing_user(manager, user_id):
    websocket1 = make_websocket()
    websocket2 = make_websocket()
    manager._connections[user_id].add(websocket1)

    manager.disconnect(user_id, websocket2)

    assert manager.has_user(user_id) is True
    assert websocket1 in manager._connections[user_id]
    assert len(manager._connections[user_id]) == 1


@pytest.mark.unit
async def test_send_to_user_sends_message_to_all_active_connections(manager, user_id):
    websocket1 = make_websocket()
    websocket2 = make_websocket()
    message = {"type": "invite_received", "from_user_id": "123"}

    manager._connections[user_id].add(websocket1)
    manager._connections[user_id].add(websocket2)

    await manager.send_to_user(user_id, message)

    websocket1.send_json.assert_awaited_once_with(message)
    websocket2.send_json.assert_awaited_once_with(message)
    assert manager.has_user(user_id) is True


@pytest.mark.unit
async def test_send_to_user_does_nothing_when_user_has_no_connections(manager, user_id):
    message = {"type": "invite_received"}

    await manager.send_to_user(user_id, message)

    assert manager.has_user(user_id) is False


@pytest.mark.unit
async def test_send_to_user_removes_dead_connections_and_keeps_live_ones(manager, user_id):
    live_websocket = make_websocket()
    dead_websocket = make_websocket()
    dead_websocket.send_json.side_effect = Exception("socket closed")

    manager._connections[user_id].add(live_websocket)
    manager._connections[user_id].add(dead_websocket)

    message = {"type": "ping"}

    await manager.send_to_user(user_id, message)

    live_websocket.send_json.assert_awaited_once_with(message)
    dead_websocket.send_json.assert_awaited_once_with(message)

    assert manager.has_user(user_id) is True
    assert live_websocket in manager._connections[user_id]
    assert dead_websocket not in manager._connections[user_id]


@pytest.mark.unit
async def test_send_to_user_removes_user_when_all_connections_are_dead(manager, user_id):
    dead_websocket1 = make_websocket()
    dead_websocket2 = make_websocket()
    dead_websocket1.send_json.side_effect = Exception("socket closed")
    dead_websocket2.send_json.side_effect = Exception("socket closed")

    manager._connections[user_id].add(dead_websocket1)
    manager._connections[user_id].add(dead_websocket2)

    message = {"type": "ping"}

    await manager.send_to_user(user_id, message)

    assert manager.has_user(user_id) is False
    assert user_id not in manager._connections


def test_has_user_returns_false_when_user_not_connected(manager, user_id):
    assert manager.has_user(user_id) is False


def test_has_user_returns_true_when_user_has_connections(manager, user_id):
    websocket = make_websocket()
    manager._connections[user_id].add(websocket)

    assert manager.has_user(user_id) is True


@pytest.mark.unit
async def test_in_memory_notifier_delegates_to_manager_send_to_user(monkeypatch, user_id):
    manager = realtime_module.ConnectionManager()
    notifier = realtime_module.InMemoryNotifier(manager)
    message = {"type": "invite_received"}

    called = {}

    async def fake_send_to_user(passed_user_id, passed_message):
        called["user_id"] = passed_user_id
        called["message"] = passed_message

    monkeypatch.setattr(manager, "send_to_user", fake_send_to_user)

    await notifier.notify_user(user_id, message)

    assert called["user_id"] == user_id
    assert called["message"] == message


def test_get_notifier_returns_module_notifier_instance():
    result = realtime_module.get_notifier()

    assert result is realtime_module.notifier
    

@pytest.mark.unit
async def test_send_to_user_with_invite_response_json_payload(manager, user_id):
    websocket = make_websocket()
    manager._connections[user_id].add(websocket)

    payload = {
        "type": "invite_created",
        "invite": {
            "id": str(uuid.uuid4()),
            "from_player_id": str(uuid.uuid4()),
            "to_player_id": str(uuid.uuid4()),
            "is_open": True,
            "created_at": "2026-03-13T12:00:00+00:00",
            "responded_at": None,
        },
    }

    await manager.send_to_user(user_id, payload)

    websocket.send_json.assert_awaited_once_with(payload)
