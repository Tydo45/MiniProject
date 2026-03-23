import uuid

import chess
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from chess_service.api_models import GameEventResponse
from chess_service.auth import (
    get_current_user_id,
    get_game_require_user_has_next_turn,
    get_game_require_user_is_player,
)
from chess_service.db import get_db
from chess_service.models import Game, GameEvent
from chess_service.realtime import RealtimeNotifier, get_notifier

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class moveRequest(BaseModel):
    uci: str


@router.post("/games/{game_id}/move")
async def move(
    move: moveRequest,
    user_id: uuid.UUID = Depends(
        get_current_user_id
    ),  # Force Valid User ID, passed to get_game_require_user_has_next_turn
    game: Game = Depends(get_game_require_user_has_next_turn),  # Force Valid Game ID & Next Turn
    db: Session = Depends(get_db),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> GameEventResponse:
    """
    Make a move for a User.

    Requires a valid JWT. Requires User to be part of the Game and
    user is next to move.

    Args:
        move: Request body containing the game id and move's uci.
        user_id: Authenticated user ID extracted from JWT.
        db: SQLAlchemy database session.

    Returns:
        GameEventResponse: The created GameEvent.
    """
    next_ply = game.events[-1].ply + 1 if game.events else 1

    board = chess.Board()

    for event in game.events:
        board.push_uci(event.uci_move)

    try:
        m = chess.Move.from_uci(move.uci)
        if m not in board.legal_moves:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Illegal Move",
            )
    except chess.InvalidMoveError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UCI",
        ) from err

    gameEvent = GameEvent(game_id=game.id, ply=next_ply, uci_move=move.uci)
    db.add(gameEvent)
    db.commit()
    db.refresh(gameEvent)

    for player_id in [game.white_player_id, game.black_player_id]:
        await notifier.notify_user(
            player_id,
            {
                "type": "game_updated",
                "gameId": str(game.id),
            },
        )

    return GameEventResponse.model_validate(gameEvent)


@router.post("/games/{game_id}/draw")
async def draw(
    game_id: uuid.UUID,  # Needed for route, required by get_game_require_user_has_next_turn
    user_id: uuid.UUID = Depends(get_current_user_id),
    game: Game = Depends(get_game_require_user_has_next_turn),
    db: Session = Depends(get_db),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> None:
    """
    Request a Draw.

    Requires a valid JWT. Requires User to be part of the Game and
    user is next to move.

    Args:
        user_id: Authenticated user ID extracted from JWT.
        db: SQLAlchemy database session.

    Returns:
        None.
    """
    if game.draw_offered_by:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Draw offer awaiting response",
        )

    game.draw_offered_by = user_id
    db.commit()
    db.refresh(game)

    opposing_player_id = (
        game.black_player_id if game.black_player_id != user_id else game.white_player_id
    )

    await notifier.notify_user(
        opposing_player_id,
        {
            "type": "draw_proposed",
            "gameId": str(game.id),
        },
    )


@router.post("/games/{game_id}/draw/accept")
async def accept_draw(
    game_id: uuid.UUID,  # Needed for route, required by get_game_require_user_is_player
    user_id: uuid.UUID = Depends(get_current_user_id),
    game: Game = Depends(get_game_require_user_is_player),
    db: Session = Depends(get_db),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> None:
    """
    Accept a draw request.

    Requires a valid JWT. Requires User to be part of the Game and
    user is next to move.

    Args:
        user_id: Authenticated user ID extracted from JWT.
        db: SQLAlchemy database session.

    Returns:
        None.
    """
    if not game.draw_offered_by or game.draw_offered_by == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Draw not Offered by Opponent",
        )

    opposing_player_id = (
        game.black_player_id if game.black_player_id != user_id else game.white_player_id
    )

    game.is_draw = True
    game.draw_offered_by = None
    db.commit()
    db.refresh(game)

    await notifier.notify_user(
        opposing_player_id,
        {
            "type": "draw_accepted",
            "gameId": str(game.id),
        },
    )


@router.post("/games/{game_id}/draw/decline")
async def decline_draw(
    game_id: uuid.UUID,  # Needed for route, required by get_game_require_user_is_player
    user_id: uuid.UUID = Depends(get_current_user_id),
    game: Game = Depends(get_game_require_user_is_player),
    db: Session = Depends(get_db),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> None:
    """
    Decline a draw request.

    Requires a valid JWT. Requires User to be part of the Game and
    user is next to move.

    Args:
        user_id: Authenticated user ID extracted from JWT.
        db: SQLAlchemy database session.

    Returns:
        None.
    """
    if not game.draw_offered_by or game.draw_offered_by == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Draw not Offered by Opponent",
        )

    opposing_player_id = (
        game.black_player_id if game.black_player_id != user_id else game.white_player_id
    )

    game.draw_offered_by = None
    db.commit()
    db.refresh(game)

    await notifier.notify_user(
        opposing_player_id,
        {
            "type": "draw_declined",
            "gameId": str(game.id),
        },
    )


@router.post("/games/{game_id}/resign")
def resign(
    game_id: uuid.UUID = Depends(
        get_game_require_user_is_player
    ),  # Needed for route, required by get_game_require_user_has_next_turn
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None: ...


@router.post("/games")
def game(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None: ...
