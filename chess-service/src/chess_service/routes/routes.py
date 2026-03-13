import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from chess_service.api_models import GameEventResponse
from chess_service.auth import get_current_user_id
from chess_service.db import get_db
from chess_service.models import Game, GameEvent

import chess

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class moveRequest(BaseModel):
    game_id: uuid.UUID
    uci: str


@router.post("/move")
def move(
    move: moveRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> GameEventResponse:
    """
    Make a move for a User

    Requires a valid JWT.

    Args:
        move: Request body containing the game id and move's uci.
        user_id: Authenticated user ID extracted from JWT.
        db: SQLAlchemy database session.

    Returns:
        GameEventResponse: The created GameEvent.
    """
    stmt = select(Game).where(Game.id == move.game_id)
    game = db.execute(stmt).scalar_one_or_none()

    if not game:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Game Id",
        )

    if user_id not in (game.white_player_id, game.black_player_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not Allowed",
        )

    stmt = (
        select(GameEvent)
        .where(GameEvent.game_id == move.game_id)
        .order_by(GameEvent.ply)
    )
    game_events = db.execute(stmt).scalars().all()

    next_ply = game_events[-1].ply + 1 if game_events else 1

    # (User is white & next ply is odd) or (User is black & next ply is even)
    if (user_id == game.white_player_id and next_ply % 2 == 1) or (user_id == game.black_player_id and next_ply % 2 == 0):
        # Validate Move
        board = chess.Board()
    
        for event in game_events:
            board.push_uci(event.uci_move)
            
        m = chess.Move.from_uci(move.uci)
        if m not in board.legal_moves:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Move",
            )
        
        # Insert Move into db
        gameEvent = GameEvent(
            game_id = game.id,
            ply = next_ply,
            move = move.uci
        )
        db.add(gameEvent)
        db.commit()
        db.refresh(gameEvent)
        
        return GameEventResponse.model_validate(gameEvent)
        
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not Allowed",
    )


@router.post("/draw")
def draw(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None: ...


@router.post("/resign")
def resign(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None: ...


@router.post("/game")
def game(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None: ...
