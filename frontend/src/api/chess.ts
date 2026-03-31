import type { GameEventResponse, GamesResponse } from "../types/game";

const CHESS_API_BASE = "/api/chess";

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: string };
    if (typeof data.detail === "string" && data.detail.length > 0) {
      return data.detail;
    }
  } catch {
    return response.statusText || "Request failed";
  }

  return response.statusText || "Request failed";
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function chessRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const accessToken = localStorage.getItem("access_token");

  if (!accessToken) {
    throw new ApiError("Not authenticated", 401);
  }

  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);

  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${CHESS_API_BASE}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), response.status);
  }

  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function listGames(): Promise<GamesResponse> {
  return chessRequest<GamesResponse>("/games", { method: "POST" });
}

export function makeMove(gameId: string, uci: string): Promise<GameEventResponse> {
  return chessRequest<GameEventResponse>(`/games/${gameId}/move`, {
    method: "POST",
    body: JSON.stringify({ uci }),
  });
}

export function offerDraw(gameId: string): Promise<void> {
  return chessRequest<void>(`/games/${gameId}/draw`, { method: "POST" });
}

export function acceptDraw(gameId: string): Promise<void> {
  return chessRequest<void>(`/games/${gameId}/draw/accept`, { method: "POST" });
}

export function declineDraw(gameId: string): Promise<void> {
  return chessRequest<void>(`/games/${gameId}/draw/decline`, { method: "POST" });
}

export function resign(gameId: string): Promise<void> {
  return chessRequest<void>(`/games/${gameId}/resign`, { method: "POST" });
}
