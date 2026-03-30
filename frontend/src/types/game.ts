export interface CreateGameRequest {
  white_player_id: string;
  black_player_id: string;
}

export interface MoveRequest {
  uci: string;
}

export interface GameEventResponse {
  id: string;
  game_id: string;
  ply: number;
  uci_move: string;
  created_at: string;
}

export interface GameResponse {
  id: string;

  white_player_id: string;
  black_player_id: string;
  winner_player_id: string | null;

  is_draw: boolean;

  created_at: string;

  events: GameEventResponse[];
}

export interface GamesResponse {
  games: GameResponse[];
}

export interface GameUpdatedMessage      { type: "game_updated";      gameId: string }
export interface DrawProposedMessage     { type: "draw_proposed";     gameId: string }
export interface DrawAcceptedMessage     { type: "draw_accepted";     gameId: string }
export interface DrawDeclinedMessage     { type: "draw_declined";     gameId: string }
export interface OpponentResignedMessage { type: "opponent_resigned"; gameId: string }
export interface GamePongMessage         { type: "pong" }

export type GameSocketMessage =
  | GameUpdatedMessage
  | DrawProposedMessage
  | DrawAcceptedMessage
  | DrawDeclinedMessage
  | OpponentResignedMessage
  | GamePongMessage;