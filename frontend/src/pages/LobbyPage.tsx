import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCurrentUserIdFromToken, getStoredAccessToken } from "../api/auth";
import { listGames } from "../api/chess";
import {
  acceptInvite,
  ApiError,
  listInvites,
  listOpenLobbies,
  readyLobby,
  sendInvite,
} from "../api/lobby";
import { connectLobbySocket } from "../api/socket";
import type {
  InviteResponse,
  LobbyResponse,
  LobbySocketMessage,
  OpenLobbyResponse,
} from "../types/lobby";
import type { GameResponse } from "../types/game";
import "../LobbyPage.css";

const ACTIVE_LOBBY_STORAGE_KEY = "active_lobby";
const SOCKET_RECONNECT_DELAY_MS = 3000;

type LobbyTab = "invites" | "open";
type ConnectionState = "connecting" | "live" | "offline";

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function shortId(value: string): string {
  if (value.length <= 14) {
    return value;
  }

  return `${value.slice(0, 8)}...${value.slice(-4)}`;
}

function getStoredActiveLobby(): LobbyResponse | null {
  const storedLobby = localStorage.getItem(ACTIVE_LOBBY_STORAGE_KEY);

  if (!storedLobby) {
    return null;
  }

  try {
    return JSON.parse(storedLobby) as LobbyResponse;
  } catch {
    localStorage.removeItem(ACTIVE_LOBBY_STORAGE_KEY);
    return null;
  }
}

function isUserInLobby(lobby: LobbyResponse, userId: string): boolean {
  return lobby.player_id_1 === userId || lobby.player_id_2 === userId;
}

function updateLobbyReadyState(
  lobby: LobbyResponse,
  userId: string | null,
  options: { bothReady?: boolean; markOpponentReady?: boolean } = {},
): LobbyResponse {
  const nextLobby = { ...lobby };

  if (options.markOpponentReady) {
    if (userId === lobby.player_id_1) {
      nextLobby.player_2_ready = true;
    } else if (userId === lobby.player_id_2) {
      nextLobby.player_1_ready = true;
    }
  } else if (userId === lobby.player_id_1) {
    nextLobby.player_1_ready = true;
  } else if (userId === lobby.player_id_2) {
    nextLobby.player_2_ready = true;
  }

  if (options.bothReady) {
    nextLobby.player_1_ready = true;
    nextLobby.player_2_ready = true;
  }

  return nextLobby;
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.length > 0) {
    return error.message;
  }

  return fallback;
}

export default function LobbyPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<LobbyTab>("invites");
  const [currentUserId, setCurrentUserId] = useState<string | null>(() =>
    getCurrentUserIdFromToken(),
  );
  const [openLobbies, setOpenLobbies] = useState<OpenLobbyResponse[]>([]);
  const [invites, setInvites] = useState<InviteResponse[]>([]);
  const [openGames, setOpenGames] = useState<GameResponse[]>([]);
  const [activeLobby, setActiveLobby] = useState<LobbyResponse | null>(() =>
    getStoredActiveLobby(),
  );
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("connecting");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [pageError, setPageError] = useState("");
  const [inviteeId, setInviteeId] = useState("");
  const [inviteError, setInviteError] = useState("");
  const [inviteSuccess, setInviteSuccess] = useState("");
  const [inviteSubmitting, setInviteSubmitting] = useState(false);
  const [acceptingInviteId, setAcceptingInviteId] = useState<string | null>(
    null,
  );
  const [readying, setReadying] = useState(false);
  const [lobbyNotice, setLobbyNotice] = useState("");

  const hasActiveLobby = activeLobby !== null;
  const accessToken = getStoredAccessToken();

  const currentPlayerNumber = useMemo(() => {
    if (!activeLobby || !currentUserId) {
      return null;
    }

    if (activeLobby.player_id_1 === currentUserId) {
      return 1;
    }

    if (activeLobby.player_id_2 === currentUserId) {
      return 2;
    }

    return null;
  }, [activeLobby, currentUserId]);

  const isCurrentUserReady = useMemo(() => {
    if (!activeLobby || currentPlayerNumber === null) {
      return false;
    }

    return currentPlayerNumber === 1
      ? activeLobby.player_1_ready
      : activeLobby.player_2_ready;
  }, [activeLobby, currentPlayerNumber]);

  const handleUnauthorized = useCallback(() => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem(ACTIVE_LOBBY_STORAGE_KEY);
    navigate("/", { replace: true });
  }, [navigate]);

  const loadLobbyData = useCallback(
    async (manual = false) => {
      if (manual) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setPageError("");

      try {
        const [nextOpenLobbies, nextInvites, nextOpenGames] = await Promise.all([
          listOpenLobbies(),
          listInvites(),
          listGames(),
        ]);

        setOpenLobbies(nextOpenLobbies);
        setInvites(nextInvites);
        setOpenGames(nextOpenGames.games);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          handleUnauthorized();
          return;
        }

        setPageError(getErrorMessage(error, "Unable to load lobby data."));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [handleUnauthorized],
  );

  useEffect(() => {
    if (!accessToken) {
      handleUnauthorized();
      return;
    }

    const userId = getCurrentUserIdFromToken();
    if (!userId) {
      handleUnauthorized();
      return;
    }

    setCurrentUserId(userId);
    void loadLobbyData();
  }, [accessToken, handleUnauthorized, loadLobbyData]);

  useEffect(() => {
    if (activeLobby) {
      localStorage.setItem(ACTIVE_LOBBY_STORAGE_KEY, JSON.stringify(activeLobby));
    } else {
      localStorage.removeItem(ACTIVE_LOBBY_STORAGE_KEY);
    }
  }, [activeLobby]);

  useEffect(() => {
    if (activeLobby && currentUserId && !isUserInLobby(activeLobby, currentUserId)) {
      setActiveLobby(null);
    }
  }, [activeLobby, currentUserId]);

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    let disposed = false;
    let reconnectTimer: number | undefined;
    let socket: WebSocket | null = null;

    const handleSocketMessage = (message: LobbySocketMessage) => {
      if (message.type === "invite_created") {
        if (message.invite.to_player_id !== currentUserId) {
          return;
        }

        setInvites((currentInvites) => {
          const nextInvites = currentInvites.filter(
            (invite) => invite.id !== message.invite.id,
          );
          return [message.invite, ...nextInvites];
        });
        setInviteError("");
        return;
      }

      if (message.type === "invite_accepted") {
        if (!currentUserId || !isUserInLobby(message.lobby, currentUserId)) {
          return;
        }

        setActiveLobby(message.lobby);
        setLobbyNotice("Lobby created. Ready up when you’re set.");
        return;
      }

      if (message.type === "user_ready") {
        setActiveLobby((currentLobby) => {
          if (!currentLobby) {
            return currentLobby;
          }

          return updateLobbyReadyState(currentLobby, currentUserId, {
            bothReady: message.ReadyResponse.both_ready,
            markOpponentReady: true,
          });
        });

        if (message.ReadyResponse.game_id) {
          setActiveLobby(null);
          navigate(`/game/${message.ReadyResponse.game_id}`);
          return;
        }

        if (message.ReadyResponse.both_ready) {
          setLobbyNotice("Both players are ready. Waiting for game start.");
        }
      }
    };

    const openSocket = () => {
      if (disposed) {
        return;
      }

      setConnectionState("connecting");

      socket = connectLobbySocket(accessToken, {
        onClose: () => {
          if (disposed) {
            return;
          }

          setConnectionState("offline");
          reconnectTimer = window.setTimeout(openSocket, SOCKET_RECONNECT_DELAY_MS);
        },
        onError: () => {
          if (!disposed) {
            setConnectionState("offline");
          }
        },
        onMessage: handleSocketMessage,
        onOpen: () => {
          if (!disposed) {
            setConnectionState("live");
          }
        },
      });
    };

    openSocket();

    return () => {
      disposed = true;
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
      }
      socket?.close();
    };
  }, [accessToken, currentUserId, navigate]);

  async function handleSendInvite(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (hasActiveLobby) {
      return;
    }

    setInviteSubmitting(true);
    setInviteError("");
    setInviteSuccess("");

    try {
      const invite = await sendInvite(inviteeId.trim());
      setInviteeId("");
      setInviteSuccess(`Invite sent to ${shortId(invite.to_player_id)}.`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        handleUnauthorized();
        return;
      }

      setInviteError(getErrorMessage(error, "Unable to send invite."));
    } finally {
      setInviteSubmitting(false);
    }
  }

  async function handleAcceptInvite(inviteId: string) {
    if (hasActiveLobby) {
      return;
    }

    setAcceptingInviteId(inviteId);
    setInviteError("");
    setInviteSuccess("");
    setLobbyNotice("");

    try {
      const lobby = await acceptInvite(inviteId);
      setActiveLobby(lobby);
      setInvites((currentInvites) =>
        currentInvites.filter((invite) => invite.id !== inviteId),
      );
      setLobbyNotice("Lobby created. Ready up when you’re set.");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        handleUnauthorized();
        return;
      }

      setInviteError(getErrorMessage(error, "Unable to accept invite."));
    } finally {
      setAcceptingInviteId(null);
    }
  }

  async function handleReadyUp() {
    if (!activeLobby || !currentUserId) {
      return;
    }

    setReadying(true);
    setPageError("");
    setLobbyNotice("");

    try {
      const readyResponse = await readyLobby(activeLobby.id);
      const nextLobby = updateLobbyReadyState(activeLobby, currentUserId, {
        bothReady: readyResponse.both_ready,
      });

      setActiveLobby(nextLobby);

      if (readyResponse.game_id) {
        setActiveLobby(null);
        navigate(`/game/${readyResponse.game_id}`);
        return;
      }

      setLobbyNotice(
        readyResponse.both_ready
          ? "Both players are ready. Waiting for game start."
          : "Ready status saved. Waiting on your opponent.",
      );
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        handleUnauthorized();
        return;
      }

      setPageError(getErrorMessage(error, "Unable to ready up."));
    } finally {
      setReadying(false);
    }
  }

  return (
    <div className="page">
      <div className="container lobby-shell">
        <div className="lobby-header">
          <div>
            <p className="eyebrow">Matchmaking</p>
            <h1>Lobby</h1>
          </div>

          <div className="lobby-header-actions">
            <span className={`status-pill status-pill-${connectionState}`}>
              {connectionState === "live"
                ? "Live"
                : connectionState === "connecting"
                  ? "Connecting"
                  : "Offline"}
            </span>

            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                void loadLobbyData(true);
              }}
              disabled={loading || refreshing}
            >
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>

        <div className="lobby-meta">
          <span className="meta-label">Signed in as</span>
          <code className="mono-pill">{currentUserId ?? "Unknown user"}</code>
        </div>

        {activeLobby && (
          <section className="lobby-card active-lobby-card">
            <div className="card-heading">
              <div>
                <p className="eyebrow">Active Lobby</p>
                <h2>Ready to start</h2>
              </div>
              <p className="helper-text">
                Created {formatTimestamp(activeLobby.created_at)}
              </p>
            </div>

            <div className="player-grid">
              <div className="player-card">
                <span className="meta-label">
                  {currentPlayerNumber === 1 ? "You" : "Player One"}
                </span>
                <strong>{shortId(activeLobby.player_id_1)}</strong>
                <span
                  className={`readiness-pill ${
                    activeLobby.player_1_ready ? "ready" : "waiting"
                  }`}
                >
                  {activeLobby.player_1_ready ? "Ready" : "Waiting"}
                </span>
              </div>

              <div className="player-card">
                <span className="meta-label">
                  {currentPlayerNumber === 2 ? "You" : "Player Two"}
                </span>
                <strong>{shortId(activeLobby.player_id_2)}</strong>
                <span
                  className={`readiness-pill ${
                    activeLobby.player_2_ready ? "ready" : "waiting"
                  }`}
                >
                  {activeLobby.player_2_ready ? "Ready" : "Waiting"}
                </span>
              </div>
            </div>

            <div className="card-footer">
              <button
                type="button"
                onClick={() => {
                  void handleReadyUp();
                }}
                disabled={readying || isCurrentUserReady}
              >
                {readying
                  ? "Saving..."
                  : isCurrentUserReady
                    ? "Ready Locked In"
                    : "Ready Up"}
              </button>

              <p className="helper-text">
                Only one active lobby is supported in this first pass.
              </p>
            </div>

            {lobbyNotice && <p className="success">{lobbyNotice}</p>}
          </section>
        )}

        {openGames.length > 0 && (
          <section className="lobby-card">
            <div className="card-heading">
              <div>
                <p className="eyebrow">In Progress</p>
                <h2>Your open games</h2>
              </div>
            </div>

            <div className="list-stack">
              {openGames.map((game) => {
                const moveCount = game.events.length;
                const isYourTurn =
                  (moveCount % 2 === 0 && game.white_player_id === currentUserId) ||
                  (moveCount % 2 === 1 && game.black_player_id === currentUserId);

                return (
                  <article className="list-item" key={game.id}>
                    <div>
                      <strong>
                        {shortId(game.white_player_id)} vs {shortId(game.black_player_id)}
                      </strong>
                      <p className="helper-text">
                        Started {formatTimestamp(game.created_at)} · {moveCount} move
                        {moveCount !== 1 ? "s" : ""}
                      </p>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      {isYourTurn && (
                        <span className="readiness-pill ready">Your turn</span>
                      )}
                      <button
                        type="button"
                        onClick={() => navigate(`/game/${game.id}`)}
                      >
                        Resume
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        )}

        <div className="tabs lobby-tabs">
          <button
            type="button"
            className={activeTab === "invites" ? "active" : ""}
            onClick={() => setActiveTab("invites")}
          >
            Invites
          </button>
          <button
            type="button"
            className={activeTab === "open" ? "active" : ""}
            onClick={() => setActiveTab("open")}
          >
            Open Lobbies
          </button>
        </div>

        {pageError && <p className="error">{pageError}</p>}

        {loading ? (
          <div className="empty-state">
            <p>Loading lobby data...</p>
          </div>
        ) : activeTab === "invites" ? (
          <div className="lobby-grid">
            <section className="lobby-card">
              <div className="card-heading">
                <div>
                  <p className="eyebrow">Invite</p>
                  <h2>Challenge a player</h2>
                </div>
                <p className="helper-text">Enter a player UUID to send an invite.</p>
              </div>

              <form onSubmit={handleSendInvite}>
                <div>
                  <label htmlFor="invitee-id">Player UUID</label>
                  <input
                    id="invitee-id"
                    value={inviteeId}
                    onChange={(event) => setInviteeId(event.target.value)}
                    placeholder="00000000-0000-0000-0000-000000000000"
                    required
                    disabled={inviteSubmitting || hasActiveLobby}
                  />
                </div>

                <button type="submit" disabled={inviteSubmitting || hasActiveLobby}>
                  {inviteSubmitting ? "Sending..." : "Send Invite"}
                </button>
              </form>

              {hasActiveLobby && (
                <p className="helper-text">
                  Sending is disabled while you already have an active lobby.
                </p>
              )}

              {inviteError && <p className="error">{inviteError}</p>}
              {inviteSuccess && <p className="success">{inviteSuccess}</p>}
            </section>

            <section className="lobby-card">
              <div className="card-heading">
                <div>
                  <p className="eyebrow">Incoming</p>
                  <h2>Incoming invites</h2>
                </div>
                <p className="helper-text">
                  Accept an invite to create your next lobby.
                </p>
              </div>

              {invites.length === 0 ? (
                <div className="empty-state compact">
                  <p>No open invites right now.</p>
                </div>
              ) : (
                <div className="list-stack">
                  {invites.map((invite) => (
                    <article className="list-item" key={invite.id}>
                      <div>
                        <strong>{shortId(invite.from_player_id)}</strong>
                        <p className="helper-text">
                          Sent {formatTimestamp(invite.created_at)}
                        </p>
                      </div>

                      <button
                        type="button"
                        onClick={() => {
                          void handleAcceptInvite(invite.id);
                        }}
                        disabled={hasActiveLobby || acceptingInviteId === invite.id}
                      >
                        {acceptingInviteId === invite.id ? "Accepting..." : "Accept"}
                      </button>
                    </article>
                  ))}
                </div>
              )}
            </section>
          </div>
        ) : (
          <section className="lobby-card">
            <div className="card-heading">
              <div>
                <p className="eyebrow">Browse</p>
                <h2>Open lobbies</h2>
              </div>
              <p className="helper-text">
                Browse what is available now. Joining is not supported yet.
              </p>
            </div>

            {openLobbies.length === 0 ? (
              <div className="empty-state compact">
                <p>No open lobbies are available right now.</p>
              </div>
            ) : (
              <div className="open-lobbies-grid">
                {openLobbies.map((lobby) => (
                  <article className="list-item open-lobby-item" key={lobby.id}>
                    <div>
                      <span className="meta-label">Host</span>
                      <strong>{shortId(lobby.host_player_id)}</strong>
                      <p className="helper-text">
                        Opened {formatTimestamp(lobby.created_at)}
                      </p>
                    </div>
                    <span className="read-only-pill">Read only</span>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
