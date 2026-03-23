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

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class moveRequest(BaseModel):
    uci: str


@router.post("/games/{game_id}/move")
def move(
    move: moveRequest,
    user_id: uuid.UUID = Depends(
        get_current_user_id
    ),  # Force Valid User ID, passed to get_game_require_user_has_next_turn
    game: Game = Depends(get_game_require_user_has_next_turn),  # Force Valid Game ID & Next Turn
    db: Session = Depends(get_db),
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

    return GameEventResponse.model_validate(gameEvent)


@router.post("/games/{game_id}/draw")
def draw(
    game_id: uuid.UUID,  # Needed for route, required by get_game_require_user_has_next_turn
    user_id: uuid.UUID = Depends(get_current_user_id),
    game: Game = Depends(get_game_require_user_has_next_turn),
    db: Session = Depends(get_db),
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
    # TODO:
    ...


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
