export type InviteResponse = {
  id: string;
  from_player_id: string;
  to_player_id: string;
  is_open: boolean;
  created_at: string;
  responded_at: string | null;
};

export type OpenLobbyResponse = {
  id: string;
  host_player_id: string;
  is_open: boolean;
  created_at: string;
  joined_at: string | null;
};

export type LobbyResponse = {
  id: string;
  player_id_1: string;
  player_id_2: string;
  player_1_ready: boolean;
  player_2_ready: boolean;
  created_at: string;
};

export type ReadyResponse = {
  game_id: string | null;
  both_ready: boolean;
};

export type InviteCreatedMessage = {
  type: "invite_created";
  invite: InviteResponse;
};

export type InviteAcceptedMessage = {
  type: "invite_accepted";
  lobby: LobbyResponse;
};

export type UserReadyMessage = {
  type: "user_ready";
  ReadyResponse: ReadyResponse;
};

export type PongMessage = {
  type: "pong";
};

export type LobbySocketMessage =
  | InviteCreatedMessage
  | InviteAcceptedMessage
  | UserReadyMessage
  | PongMessage;
