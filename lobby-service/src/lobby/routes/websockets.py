import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from lobby.auth import get_current_websocket_user_id
from lobby.realtime import manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: uuid.UUID = Depends(get_current_websocket_user_id),
) -> None:
    """
    Open a websocket connection for realtime lobby events.

    The client must provide a valid JWT.
    """
    await manager.connect(user_id, websocket)

    try:
        while True:
            message = await websocket.receive_text()

            if message == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception:
        manager.disconnect(user_id, websocket)
        await websocket.close()
