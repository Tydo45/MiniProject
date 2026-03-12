import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InviteResponse(BaseModel):
    id: uuid.UUID
    from_player_id: uuid.UUID
    to_player_id: uuid.UUID
    is_open: bool
    created_at: datetime
    responded_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class OpenLobbyResponse(BaseModel):
    id: uuid.UUID
    host_player_id: uuid.UUID
    is_open: bool
    created_at: datetime
    joined_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class LobbyResponse(BaseModel):
    id: uuid.UUID
    player_id_1: uuid.UUID
    player_id_2: uuid.UUID
    player_1_ready: bool
    player_2_ready: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
