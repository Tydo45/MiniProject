import uuid

import chess
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from chess_service.api_models import GameEventResponse, GameResponse
from chess_service.auth import (
    get_current_user_id,
    get_game_require_user_has_next_turn,
    get_game_require_user_is_player,
    verify_service_token,
)
from chess_service.db import get_db
from chess_service.models import Game, GameEvent
from chess_service.realtime import RealtimeNotifier, get_notifier

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class GamesResponse(BaseModel):
    games: list[GameResponse]


@router.post("/games")
def game(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> GamesResponse:
    """
    Lists all open games the user is playing in.

    Requires a valid JWT. Requires User to be part of the Game and
    user is next to move.

    Args:
        user_id: Authenticated user ID extracted from JWT.
        db: SQLAlchemy database session.

    Returns:
        GamesResponse: contains a list of all open games the user is in
    """
    stmt = select(Game).where(
        or_(Game.white_player_id == user_id, Game.black_player_id == user_id),
        Game.winner_player_id.is_(None),
        Game.is_draw.is_(False),
    )
    games = db.execute(stmt).scalars().all()

    return GamesResponse(games=[GameResponse.model_validate(game) for game in games])


class CreateGameRequest(BaseModel):
    white_player_id: uuid.UUID
    black_player_id: uuid.UUID


@router.post("/games/create")
def create_game(
    createGameRequest: CreateGameRequest,
    _: None = Depends(verify_service_token),
    db: Session = Depends(get_db),
) -> GameResponse:
    """
    Create a Instance with for the Associated Players.

    Only callable from lobby-service.

    Args:
        user_id: Authenticated user ID extracted from JWT.
        db: SQLAlchemy database session.

    Returns:
        GameResponse: the created game
    """
    game = Game(
        white_player_id=createGameRequest.white_player_id,
        black_player_id=createGameRequest.black_player_id,
    )
    db.add(game)
    db.commit()
    db.refresh(game)

    return GameResponse.model_validate(game)


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
        game: Authenticated game orm object
        db: SQLAlchemy database session.
        notifier: RealtimeNotifier for websocket events

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
        game_id: Passed as param in url, required by auth get_game_*
        user_id: Authenticated user ID extracted from JWT.
        game: Authenticated game orm object
        db: SQLAlchemy database session.
        notifier: RealtimeNotifier for websocket events

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
        game_id: Passed as param in url, required by auth get_game_*
        user_id: Authenticated user ID extracted from JWT.
        game: Authenticated game orm object
        db: SQLAlchemy database session.
        notifier: RealtimeNotifier for websocket events

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
        game_id: Passed as param in url, required by auth get_game_*
        user_id: Authenticated user ID extracted from JWT.
        game: Authenticated game orm object
        db: SQLAlchemy database session.
        notifier: RealtimeNotifier for websocket events

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
async def resign(
    game_id: uuid.UUID,  # Needed for route, required by get_game_require_user_is_player
    user_id: uuid.UUID = Depends(get_current_user_id),
    game: Game = Depends(
        get_game_require_user_is_player
    ),  # Needed for route, required by get_game_require_user_has_next_turn
    db: Session = Depends(get_db),
    notifier: RealtimeNotifier = Depends(get_notifier),
) -> None:
    """
    Resign from a game. Opposing Player is labelled Victor.

    Requires a valid JWT. Requires User to be part of the Game and
    user is next to move.

    Args:
        game_id: Passed as param in url, required by auth get_game_*
        user_id: Authenticated user ID extracted from JWT.
        game: Authenticated game orm object
        db: SQLAlchemy database session.
        notifier: RealtimeNotifier for websocket events

    Returns:
        None.
    """
    opposing_player_id = (
        game.black_player_id if game.black_player_id != user_id else game.white_player_id
    )
    game.winner_player_id = opposing_player_id

    db.commit()
    db.refresh(game)

    await notifier.notify_user(
        opposing_player_id,
        {
            "type": "opponent_resigned",
            "gameId": str(game.id),
        },
    )
