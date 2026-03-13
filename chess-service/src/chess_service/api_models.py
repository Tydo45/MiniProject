import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GameEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    game_id: uuid.UUID
    ply: int = Field(gt=0)
    uci_move: str = Field(min_length=4, max_length=5)
    created_at: datetime


class GameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID

    white_player_id: uuid.UUID
    black_player_id: uuid.UUID
    winner_player_id: uuid.UUID | None = None
    is_draw: bool = False

    created_at: datetime

    events: list[GameEventResponse] = []
