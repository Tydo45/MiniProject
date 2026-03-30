import uuid
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from lobby.api_models import InviteResponse, LobbyResponse, OpenLobbyResponse
from lobby.auth import get_current_user_id
from lobby.config import get_settings
from lobby.db import get_db
from lobby.models import Invite, Lobby, OpenLobby
from lobby.realtime import RealtimeNotifier, get_notifier

router = APIRouter()

security = HTTPBearer()

CHESS_SERVICE_URL = "http://chess-service:8002"


class ChessServiceClient(Protocol):
    async def create_game(
        self, white_player_id: uuid.UUID, black_player_id: uuid.UUID
    ) -> uuid.UUID: ...


class HttpxChessServiceClient:
    async def create_game(
        self, white_player_id: uuid.UUID, black_player_id: uuid.UUID
    ) -> uuid.UUID:
        settings = get_settings()
        access_token = jwt.encode(
            {
                "sub": "lobby-service",
                "type": "service",
                "exp": datetime.now(UTC) + timedelta(minutes=30),
            },
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        headers = {"Authorization": f"Bearer {access_token}"}
        chess_payload = {
            "white_player_id": str(white_player_id),
            "black_player_id": str(black_player_id),
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            http_response = await client.post(
                f"{CHESS_SERVICE_URL}/games/create",
                headers=headers,
                json=chess_payload,
            )
        http_response.raise_for_status()
        game_data = http_response.json()
        return uuid.UUID(game_data["id"])


def get_chess_service_client() -> ChessServiceClient:
    return HttpxChessServiceClient()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/open-lobbies", response_model=list[OpenLobbyResponse])
def list_open_lobbies(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[OpenLobbyResponse]:
    """
    Retrieve all currently open lobbies.

    Requires a valid JWT.

    Returns:
        list[OpenLobbyResponse]: A list of open lobbies that players can join.
    """
    stmt = select(OpenLobby).where(OpenLobby.is_open)
    lobbies = db.execute(stmt).scalars().all()

    return [OpenLobbyResponse.model_validate(lobby) for lobby in lobbies]


@router.get("/invites", response_model=list[InviteResponse])
def list_open_invites(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[InviteResponse]:
    """
    Retrieve all currently open invites for the requesting user.

    Requires a valid JWT.

    Returns:
        list[InviteResponse]: A list of open invites that the user can accept.
    """
    stmt = select(Invite).where(Invite.to_player_id == user_id, Invite.is_open)
    invites = db.execute(stmt).scalars().all()

    return [InviteResponse.model_validate(invite) for invite in invites]


class InvitationRequest(BaseModel):
    invitee_id: uuid.UUID


@router.post("/invites/send", response_model=InviteResponse)
async def send_invite(
    invite: InvitationRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> InviteResponse:
    """
    Send a game invite to another player.

    Creates a new invite record from the authenticated user to the
    specified invitee.

    Args:
        invite: Request body containing the invitee's UUID.
        user_id: Authenticated user ID extracted from JWT.
        db: SQLAlchemy database session.

    Returns:
        InviteResponse: The created invite.
    """
    # TODO: Validate invitee_id exists (Requires request to auth-service)
    if invite.invitee_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot invite yourself",
        )

    existing_stmt = select(Invite).where(
        Invite.from_player_id == user_id,
        Invite.to_player_id == invite.invitee_id,
        Invite.is_open,
    )
    existing_invite = db.execute(existing_stmt).scalar_one_or_none()

    if existing_invite is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Open invite already exists",
        )

    new_invite = Invite(
        from_player_id=user_id,
        to_player_id=invite.invitee_id,
        is_open=True,
    )

    db.add(new_invite)
    db.commit()
    db.refresh(new_invite)

    inviteResponse = InviteResponse.model_validate(new_invite)

    await notifier.notify_user(
        invite.invitee_id,
        {
            "type": "invite_created",
            "invite": inviteResponse.model_dump(mode="json"),
        },
    )

    return inviteResponse


class InvitationAcceptRequest(BaseModel):
    invite_id: uuid.UUID


@router.post("/invites/accept", response_model=LobbyResponse)
async def accept_invite(
    inviteAcceptRequest: InvitationAcceptRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> LobbyResponse:
    """
    Accept a game invite from another player.

    Creates a new lobby record for the 'from' and 'to' Players

    Args:
        inviteAcceptRequest: Request body containing the invitee's UUID.
        user_id: Authenticated user ID extracted from JWT.
        db: SQLAlchemy database session.
        notifier: Realtime notifier using Websockets.

    Returns:
        LobbyResponse: The created lobby.
    """
    stmt = select(Invite).where(Invite.id == inviteAcceptRequest.invite_id)
    invite = db.execute(stmt).scalar_one_or_none()

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite doesn't exist",
        )

    if invite.to_player_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authorized to accept invite",
        )

    invite.responded_at = datetime.now(UTC)
    invite.is_open = False

    db.commit()
    db.refresh(invite)

    lobby = Lobby(
        player_id_1=invite.from_player_id,
        player_id_2=invite.to_player_id,
    )

    db.add(lobby)
    db.commit()
    db.refresh(lobby)

    lobbyResponse = LobbyResponse.model_validate(lobby)

    await notifier.notify_user(
        invite.from_player_id,
        {
            "type": "invite_accepted",
            "lobby": lobbyResponse.model_dump(mode="json"),
        },
    )

    return lobbyResponse


class ReadyRequest(BaseModel):
    lobby_id: uuid.UUID


class ReadyResponse(BaseModel):
    game_id: uuid.UUID | None
    both_ready: bool


@router.post("/ready")
async def ready(
    ready: ReadyRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    notifier: RealtimeNotifier = Depends(get_notifier),
    chess_client: ChessServiceClient = Depends(get_chess_service_client),
) -> ReadyResponse:
    """
    Ready the user into the specified lobby.

    Creates a new game record for Players in the lobby.

    Args:
        ready: Request body containing the lobby's UUID.
        user_id: Authenticated user ID extracted from JWT.
        db: SQLAlchemy database session.
        notifier: Realtime notifier using Websockets.

    Returns:
        ReadyResponse: Response body containing game_id and both_ready boolean
    """
    stmt = select(Lobby).where(
        Lobby.id == ready.lobby_id, (Lobby.player_id_1 == user_id) | (Lobby.player_id_2 == user_id)
    )
    lobby = db.execute(stmt).scalar_one_or_none()

    if not lobby:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Lobby to Ready for",
        )

    player_num = 1 if lobby.player_id_1 == user_id else 2
    opposing_player_num = 2 if lobby.player_id_1 == user_id else 1

    setattr(lobby, f"player_{player_num}_ready", True)

    db.commit()
    db.refresh(lobby)

    both_ready = lobby.player_1_ready and lobby.player_2_ready

    if both_ready:
        game_id = await chess_client.create_game(lobby.player_id_1, lobby.player_id_2)
        ready_response = ReadyResponse(game_id=game_id, both_ready=True)

        await notifier.notify_user(
            getattr(lobby, f"player_id_{opposing_player_num}"),
            {
                "type": "user_ready",
                "ReadyResponse": ready_response.model_dump(mode="json"),
            },
        )

        return ready_response

    return ReadyResponse(game_id=None, both_ready=False)
