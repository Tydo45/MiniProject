import type {
  InviteResponse,
  LobbyResponse,
  OpenLobbyResponse,
  ReadyResponse,
} from "../types/lobby";

const LOBBY_API_BASE = "/api/lobby";

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

async function lobbyRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const accessToken = localStorage.getItem("access_token");

  if (!accessToken) {
    throw new ApiError("Not authenticated", 401);
  }

  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);

  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${LOBBY_API_BASE}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), response.status);
  }

  return response.json() as Promise<T>;
}

export function listOpenLobbies(): Promise<OpenLobbyResponse[]> {
  return lobbyRequest<OpenLobbyResponse[]>("/open-lobbies");
}

export function listInvites(): Promise<InviteResponse[]> {
  return lobbyRequest<InviteResponse[]>("/invites");
}

export function sendInvite(inviteeId: string): Promise<InviteResponse> {
  return lobbyRequest<InviteResponse>("/invites/send", {
    method: "POST",
    body: JSON.stringify({ invitee_id: inviteeId }),
  });
}

export function acceptInvite(inviteId: string): Promise<LobbyResponse> {
  return lobbyRequest<LobbyResponse>("/invites/accept", {
    method: "POST",
    body: JSON.stringify({ invite_id: inviteId }),
  });
}

export function readyLobby(lobbyId: string): Promise<ReadyResponse> {
  return lobbyRequest<ReadyResponse>("/ready", {
    method: "POST",
    body: JSON.stringify({ lobby_id: lobbyId }),
  });
}
