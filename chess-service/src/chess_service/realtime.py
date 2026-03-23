import uuid
from collections import defaultdict
from typing import Protocol

from fastapi import WebSocket


class ConnectionManager:
    """
    Track active websocket connections for connected users on this app instance.
    """

    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[user_id].add(websocket)

    def disconnect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        connections = self._connections.get(user_id)
        if connections is None:
            return

        connections.discard(websocket)

        if not connections:
            self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: uuid.UUID, message: dict) -> None:
        connections = list(self._connections.get(user_id, set()))
        dead_connections: list[WebSocket] = []

        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception:
                dead_connections.append(websocket)

        for websocket in dead_connections:
            self.disconnect(user_id, websocket)

    def has_user(self, user_id: uuid.UUID) -> bool:
        return bool(self._connections.get(user_id))


class RealtimeNotifier(Protocol):
    async def notify_user(self, user_id: uuid.UUID, message: dict) -> None:
        """
        Deliver a realtime message to a specific user.
        """
        ...


class InMemoryNotifier:
    """
    Deliver realtime events only to users connected to this app instance.
    """

    def __init__(self, manager: ConnectionManager) -> None:
        self.manager = manager

    async def notify_user(self, user_id: uuid.UUID, message: dict) -> None:
        await self.manager.send_to_user(user_id, message)


manager = ConnectionManager()
notifier = InMemoryNotifier(manager)


def get_notifier() -> RealtimeNotifier:
    return notifier
