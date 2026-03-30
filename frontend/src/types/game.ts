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