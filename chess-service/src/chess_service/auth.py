import uuid

import jwt
from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from chess_service.config import get_settings
from chess_service.db import get_db
from chess_service.models import Game

security = HTTPBearer()


def _not_authenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


def decode_user_id_from_token(token: str) -> uuid.UUID:
    """
    Decode a JWT and extract the authenticated user's UUID from the `sub` claim.

    Args:
        token: Encoded JWT bearer token.

    Returns:
        uuid.UUID: Authenticated user ID from the token subject.

    Raises:
        HTTPException: If the token is expired, invalid, missing a subject,
        or contains a non-UUID subject.
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except jwt.ExpiredSignatureError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from err
    except jwt.InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from err

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    try:
        return uuid.UUID(subject)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject is not a valid UUID",
        ) from err


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> uuid.UUID:
    """
    Extract and validate the authenticated user's UUID from a bearer token.

    Args:
        credentials: Bearer token credentials provided by FastAPI security.

    Returns:
        uuid.UUID: Authenticated user ID.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _not_authenticated()

    return decode_user_id_from_token(credentials.credentials)


def get_current_websocket_user_id(websocket: WebSocket) -> uuid.UUID:
    authorization = websocket.headers.get("Authorization")
    if not authorization:
        raise _not_authenticated()

    try:
        scheme, token = authorization.split(" ", 1)
    except ValueError as err:
        raise _not_authenticated() from err

    return get_current_user_id(
        HTTPAuthorizationCredentials(
            scheme=scheme,
            credentials=token,
        )
    )


def get_game(
    game_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Game:
    stmt = select(Game).where(Game.id == game_id)
    game = db.execute(stmt).scalar_one_or_none()

    if not game:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Game Id",
        )

    return game


def get_game_require_user_is_player(
    user_id: uuid.UUID = Depends(get_current_user_id),
    game: Game = Depends(get_game),
) -> Game:
    if user_id not in (game.white_player_id, game.black_player_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not Allowed",
        )
    return game


def get_game_require_user_has_next_turn(
    user_id: uuid.UUID = Depends(get_current_user_id),
    game: Game = Depends(get_game_require_user_is_player),
) -> Game:
    next_ply = game.events[-1].ply + 1 if game.events else 1

    if user_id not in (game.white_player_id, game.black_player_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not Allowed",
        )

    is_white_turn = next_ply % 2 == 1
    user_is_white = user_id == game.white_player_id
    user_is_black = user_id == game.black_player_id

    if (user_is_white and not is_white_turn) or (user_is_black and is_white_turn):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not next to move",
        )

    return game
