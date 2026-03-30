import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getCurrentUserIdFromToken, getStoredAccessToken } from "../api/auth";
import {
  acceptDraw,
  ApiError,
  declineDraw,
  listGames,
  makeMove,
  offerDraw,
  resign,
} from "../api/chess";
import type { GameEventResponse, GameResponse, GameSocketMessage } from "../types/game";
import "../styles/GamePage.css";

const SOCKET_RECONNECT_DELAY_MS = 3000;

// ── Board constants ────────────────────────────────────────────────

const INITIAL_ROWS = [
  ["r", "n", "b", "q", "k", "b", "n", "r"],
  ["p", "p", "p", "p", "p", "p", "p", "p"],
  [null, null, null, null, null, null, null, null],
  [null, null, null, null, null, null, null, null],
  [null, null, null, null, null, null, null, null],
  [null, null, null, null, null, null, null, null],
  ["P", "P", "P", "P", "P", "P", "P", "P"],
  ["R", "N", "B", "Q", "K", "B", "N", "R"],
] as const;

const PIECE_UNICODE: Record<string, string> = {
  K: "♔", Q: "♕", R: "♖", B: "♗", N: "♘", P: "♙",
  k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟",
};

// ── Board utility ──────────────────────────────────────────────────

type BoardCell = string | null;
type Board = BoardCell[][];

function uciToCoords(sq: string): [number, number] {
  const col = sq.charCodeAt(0) - 97; // a=0, h=7
  const row = 8 - parseInt(sq[1], 10); // rank 8 = row 0
  return [row, col];
}

function coordsToUci(row: number, col: number): string {
  return String.fromCharCode(97 + col) + String(8 - row);
}

function initialBoard(): Board {
  return INITIAL_ROWS.map((row) => [...row]) as Board;
}

function computeBoard(events: GameEventResponse[]): Board {
  const board = initialBoard();
  let enPassantTarget: [number, number] | null = null;

  for (const event of events) {
    const uci = event.uci_move;
    const [fromRow, fromCol] = uciToCoords(uci.slice(0, 2));
    const [toRow, toCol] = uciToCoords(uci.slice(2, 4));
    const promotionChar = uci.length === 5 ? uci[4] : null;
    const piece = board[fromRow][fromCol];

    if (piece === null) {
      enPassantTarget = null;
      continue;
    }

    const isWhitePiece = piece === piece.toUpperCase();

    // Track en passant target square after pawn double-push
    let nextEnPassant: [number, number] | null = null;
    if ((piece === "P" || piece === "p") && Math.abs(toRow - fromRow) === 2) {
      nextEnPassant = [(fromRow + toRow) / 2, fromCol];
    }

    // En passant capture: pawn moves diagonally onto empty square
    if (
      (piece === "P" || piece === "p") &&
      fromCol !== toCol &&
      board[toRow][toCol] === null &&
      enPassantTarget !== null &&
      enPassantTarget[0] === toRow &&
      enPassantTarget[1] === toCol
    ) {
      const capturedRow = isWhitePiece ? toRow + 1 : toRow - 1;
      board[capturedRow][toCol] = null;
    }

    // Castling: king moves 2 squares horizontally
    if (piece === "K" && fromRow === 7 && fromCol === 4) {
      if (toCol === 6) {
        // Kingside
        board[7][5] = "R";
        board[7][7] = null;
      } else if (toCol === 2) {
        // Queenside
        board[7][3] = "R";
        board[7][0] = null;
      }
    }
    if (piece === "k" && fromRow === 0 && fromCol === 4) {
      if (toCol === 6) {
        board[0][5] = "r";
        board[0][7] = null;
      } else if (toCol === 2) {
        board[0][3] = "r";
        board[0][0] = null;
      }
    }

    // Move piece
    board[fromRow][fromCol] = null;
    if (promotionChar) {
      board[toRow][toCol] = isWhitePiece
        ? promotionChar.toUpperCase()
        : promotionChar.toLowerCase();
    } else {
      board[toRow][toCol] = piece;
    }

    enPassantTarget = nextEnPassant;
  }

  return board;
}

// ── Helpers ────────────────────────────────────────────────────────

function shortId(value: string): string {
  if (value.length <= 14) return value;
  return `${value.slice(0, 8)}...${value.slice(-4)}`;
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.length > 0) return error.message;
  return fallback;
}

type ConnectionState = "connecting" | "live" | "offline";

// ── Component ──────────────────────────────────────────────────────

export default function GamePage() {
  const { id: gameId } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [game, setGame] = useState<GameResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUserId] = useState<string | null>(() => getCurrentUserIdFromToken());

  const [selectedSquare, setSelectedSquare] = useState<[number, number] | null>(null);
  const [submittingMove, setSubmittingMove] = useState(false);
  const [moveError, setMoveError] = useState<string | null>(null);

  const [drawPending, setDrawPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSubmitting, setActionSubmitting] = useState(false);

  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");

  const moveListRef = useRef<HTMLDivElement>(null);
  const accessToken = getStoredAccessToken();

  // ── Derived values ───────────────────────────────────────────────

  const board = useMemo(
    () => computeBoard(game?.events ?? []),
    [game],
  );

  const isWhiteTurn = (game?.events.length ?? 0) % 2 === 0;

  const isMyTurn =
    game !== null &&
    currentUserId !== null &&
    ((isWhiteTurn && currentUserId === game.white_player_id) ||
      (!isWhiteTurn && currentUserId === game.black_player_id));

  const isFlipped = currentUserId !== null && game !== null && currentUserId === game.black_player_id;

  const isGameOver =
    game !== null && (game.winner_player_id !== null || game.is_draw);

  // ── Auth helper ──────────────────────────────────────────────────

  const handleUnauthorized = useCallback(() => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    navigate("/", { replace: true });
  }, [navigate]);

  // ── Data loading ─────────────────────────────────────────────────

  const loadGame = useCallback(
    async (isInitialLoad = false) => {
      if (!gameId) return;
      if (isInitialLoad) setLoading(true);

      try {
        const { games } = await listGames();
        const found = games.find((g) => g.id === gameId);

        if (found) {
          setGame(found);
          setError(null);
        } else if (isInitialLoad) {
          // Game not in open games on initial load — doesn't exist or already finished.
          setError("Game not found or already finished.");
        }
        // On a WS-triggered refresh: if game is gone it just ended.
        // Preserve the last known game state so the board stays visible.
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          handleUnauthorized();
          return;
        }
        if (isInitialLoad) {
          setError(getErrorMessage(err, "Unable to load game."));
        }
      } finally {
        setLoading(false);
      }
    },
    [gameId, handleUnauthorized],
  );

  useEffect(() => {
    if (!accessToken) {
      handleUnauthorized();
      return;
    }
    void loadGame(/* isInitialLoad */ true);
  }, [accessToken, handleUnauthorized, loadGame]);

  // Auto-scroll move list to bottom when moves change
  useEffect(() => {
    if (moveListRef.current) {
      moveListRef.current.scrollTop = moveListRef.current.scrollHeight;
    }
  }, [game?.events.length]);

  // ── WebSocket ────────────────────────────────────────────────────

  useEffect(() => {
    if (!accessToken || !gameId) return;

    let disposed = false;
    let reconnectTimer: number | undefined;
    let socket: WebSocket | null = null;

    const handleMessage = (message: GameSocketMessage) => {
      if (message.type === "pong") return;

      if (message.gameId !== gameId) return;

      if (message.type === "game_updated" || message.type === "opponent_resigned") {
        void loadGame();
        return;
      }

      if (message.type === "draw_proposed") {
        setDrawPending(true);
        return;
      }

      if (message.type === "draw_accepted") {
        setDrawPending(false);
        void loadGame();
        return;
      }

      if (message.type === "draw_declined") {
        setDrawPending(false);
        return;
      }
    };

    const openSocket = () => {
      if (disposed) return;
      setConnectionState("connecting");

      const ws = new WebSocket(`ws://localhost:8002/ws?token=${accessToken}`);
      socket = ws;

      ws.onopen = () => {
        if (!disposed) setConnectionState("live");
      };

      ws.onclose = () => {
        if (disposed) return;
        setConnectionState("offline");
        reconnectTimer = window.setTimeout(openSocket, SOCKET_RECONNECT_DELAY_MS);
      };

      ws.onerror = () => {
        if (!disposed) setConnectionState("offline");
      };

      ws.onmessage = (event: MessageEvent<string>) => {
        try {
          const message = JSON.parse(event.data) as GameSocketMessage;
          handleMessage(message);
        } catch {
          // ignore parse errors
        }
      };
    };

    openSocket();

    return () => {
      disposed = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [accessToken, gameId, loadGame]);

  // ── Move handling ────────────────────────────────────────────────

  function isOwnPiece(piece: BoardCell): boolean {
    if (!piece || !currentUserId || !game) return false;
    const whitePiece = piece === piece.toUpperCase();
    return (isWhiteTurn && whitePiece && currentUserId === game.white_player_id) ||
           (!isWhiteTurn && !whitePiece && currentUserId === game.black_player_id);
  }

  async function handleSquareClick(row: number, col: number) {
    if (!game || !isMyTurn || isGameOver || submittingMove) return;

    if (selectedSquare === null) {
      if (isOwnPiece(board[row][col])) {
        setSelectedSquare([row, col]);
        setMoveError(null);
      }
      return;
    }

    const [selRow, selCol] = selectedSquare;

    if (selRow === row && selCol === col) {
      setSelectedSquare(null);
      return;
    }

    // If clicking another own piece, re-select
    if (isOwnPiece(board[row][col])) {
      setSelectedSquare([row, col]);
      setMoveError(null);
      return;
    }

    const uci = coordsToUci(selRow, selCol) + coordsToUci(row, col);
    setSelectedSquare(null);
    setSubmittingMove(true);
    setMoveError(null);

    try {
      await makeMove(game.id, uci);
      await loadGame();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        handleUnauthorized();
        return;
      }
      setMoveError(getErrorMessage(err, "Move failed."));
    } finally {
      setSubmittingMove(false);
    }
  }

  // ── Game actions ─────────────────────────────────────────────────

  async function handleOfferDraw() {
    if (!game || actionSubmitting) return;
    setActionSubmitting(true);
    setActionError(null);
    try {
      await offerDraw(game.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { handleUnauthorized(); return; }
      setActionError(getErrorMessage(err, "Unable to offer draw."));
    } finally {
      setActionSubmitting(false);
    }
  }

  async function handleAcceptDraw() {
    if (!game || actionSubmitting) return;
    setActionSubmitting(true);
    setActionError(null);
    try {
      await acceptDraw(game.id);
      setDrawPending(false);
      await loadGame();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { handleUnauthorized(); return; }
      setActionError(getErrorMessage(err, "Unable to accept draw."));
    } finally {
      setActionSubmitting(false);
    }
  }

  async function handleDeclineDraw() {
    if (!game || actionSubmitting) return;
    setActionSubmitting(true);
    setActionError(null);
    try {
      await declineDraw(game.id);
      setDrawPending(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { handleUnauthorized(); return; }
      setActionError(getErrorMessage(err, "Unable to decline draw."));
    } finally {
      setActionSubmitting(false);
    }
  }

  async function handleResign() {
    if (!game || actionSubmitting) return;
    setActionSubmitting(true);
    setActionError(null);
    try {
      await resign(game.id);
      await loadGame();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { handleUnauthorized(); return; }
      setActionError(getErrorMessage(err, "Unable to resign."));
    } finally {
      setActionSubmitting(false);
    }
  }

  // ── Board rendering ───────────────────────────────────────────────

  function renderBoard() {
    if (!game) return null;

    const ranks = isFlipped ? [7, 6, 5, 4, 3, 2, 1, 0] : [0, 1, 2, 3, 4, 5, 6, 7];
    const files = isFlipped ? [7, 6, 5, 4, 3, 2, 1, 0] : [0, 1, 2, 3, 4, 5, 6, 7];

    const rankLabels = ranks.map((r) => String(8 - r));
    const fileLabels = files.map((c) => String.fromCharCode(97 + c));

    const squares: React.ReactNode[] = [];
    for (const rankIdx of ranks) {
      for (const fileIdx of files) {
        const row = rankIdx;
        const col = fileIdx;
        const isLight = (row + col) % 2 === 0;
        const piece = board[row][col];
        const isSelected =
          selectedSquare !== null && selectedSquare[0] === row && selectedSquare[1] === col;
        const canClick = isMyTurn && !isGameOver && !submittingMove;
        const isClickablePiece = canClick && isOwnPiece(piece);
        const isClickableTarget =
          canClick &&
          selectedSquare !== null &&
          !(selectedSquare[0] === row && selectedSquare[1] === col);

        const classes = [
          "sq",
          isLight ? "light" : "dark",
          isSelected ? "selected" : "",
          isClickablePiece || isClickableTarget ? "clickable" : "",
        ]
          .filter(Boolean)
          .join(" ");

        squares.push(
          <div
            key={`${row}-${col}`}
            className={classes}
            onClick={() => {
              void handleSquareClick(row, col);
            }}
          >
            {piece ? PIECE_UNICODE[piece] : null}
          </div>,
        );
      }
    }

    return (
      <div>
        <div className="board-outer">
          <div className="rank-labels">
            {rankLabels.map((label) => (
              <span key={label}>{label}</span>
            ))}
          </div>
          <div className="chess-board">{squares}</div>
        </div>
        <div className="file-labels">
          {fileLabels.map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
      </div>
    );
  }

  // ── Move history rendering ────────────────────────────────────────

  function renderMoveList() {
    if (!game || game.events.length === 0) {
      return <p className="helper-text">No moves yet.</p>;
    }

    const pairs: Array<[GameEventResponse, GameEventResponse | null]> = [];
    for (let i = 0; i < game.events.length; i += 2) {
      pairs.push([game.events[i], game.events[i + 1] ?? null]);
    }

    return (
      <div className="move-list" ref={moveListRef}>
        {pairs.map(([white, black], idx) => (
          <div className="move-pair" key={white.id}>
            <span className="ply-num">{idx + 1}.</span>
            <span className="uci">{white.uci_move}</span>
            <span className="uci">{black ? black.uci_move : ""}</span>
          </div>
        ))}
      </div>
    );
  }

  // ── Game-over message ─────────────────────────────────────────────

  function renderGameOver() {
    if (!game || !isGameOver) return null;

    let resultLabel: string;
    let resultSub: string;

    if (game.is_draw) {
      resultLabel = "Draw";
      resultSub = "The game ended in a draw.";
    } else {
      const winnerId = game.winner_player_id;

      if (!winnerId) {
        resultLabel = "Game over";
        resultSub = "Winner unavailable.";
      } else if (winnerId === currentUserId) {
        resultLabel = "You won!";
        resultSub = `Winner: ${shortId(winnerId)}`;
      } else {
        resultLabel = "You lost.";
        resultSub = `Winner: ${shortId(winnerId)}`;
      }
    }

    return (
      <div className="game-over-card">
        <p className="result-label">{resultLabel}</p>
        <p className="result-sub">{resultSub}</p>
      </div>
    );
  }

  // ── Player labels ─────────────────────────────────────────────────

  function renderPlayerLabel(position: "top" | "bottom") {
    if (!game) return null;

    const isTopOpponent = !isFlipped ? position === "top" : position === "bottom";
    const playerId = isTopOpponent ? game.black_player_id : game.white_player_id;
    const color = isTopOpponent ? "black" : "white";
    const isPlayersTurn = isTopOpponent ? !isWhiteTurn : isWhiteTurn;
    const isMe = playerId === currentUserId;

    return (
      <div className="player-label">
        <span className={`player-color-badge ${color}`} />
        <strong>{isMe ? "You" : shortId(playerId)}</strong>
        <span className="meta-label">{color}</span>
        {isPlayersTurn && !isGameOver && <span className="turn-badge">To move</span>}
      </div>
    );
  }

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="page">
      <div className="container">
        <header className="game-header">
          <div>
            <p className="eyebrow">Chess</p>
            <h1>{gameId ? shortId(gameId) : "Game"}</h1>
          </div>
          <div className="game-header-actions">
            <span className={`status-pill status-pill-${connectionState}`}>
              {connectionState === "live"
                ? "Live"
                : connectionState === "connecting"
                  ? "Connecting"
                  : "Offline"}
            </span>
            <button
              type="button"
              onClick={() => {
                navigate("/lobby");
              }}
            >
              ← Lobby
            </button>
          </div>
        </header>

        {loading && (
          <div className="loading-state">
            <p>Loading game...</p>
          </div>
        )}

        {!loading && error && <p className="error">{error}</p>}

        {!loading && !error && game && (
          <div className="game-layout">
            {/* Left: board */}
            <div className="board-wrap">
              {renderPlayerLabel("top")}
              {renderBoard()}
              {renderPlayerLabel("bottom")}
              {moveError && <p className="error">{moveError}</p>}
              {submittingMove && <p className="helper-text">Submitting move...</p>}
            </div>

            {/* Right: panel */}
            <aside className="game-panel">
              {renderGameOver()}

              {drawPending && !isGameOver && (
                <div className="draw-offer-card">
                  <p>Your opponent offered a draw.</p>
                  <div className="card-actions">
                    <button
                      type="button"
                      className="primary"
                      onClick={() => {
                        void handleAcceptDraw();
                      }}
                      disabled={actionSubmitting}
                    >
                      Accept
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        void handleDeclineDraw();
                      }}
                      disabled={actionSubmitting}
                    >
                      Decline
                    </button>
                  </div>
                </div>
              )}

              {!isGameOver && (
                <div className="panel-card">
                  <h3>Controls</h3>
                  <div className="card-actions">
                    <button
                      type="button"
                      onClick={() => {
                        void handleOfferDraw();
                      }}
                      disabled={actionSubmitting || !isMyTurn || drawPending}
                    >
                      Offer Draw
                    </button>
                    <button
                      type="button"
                      className="danger"
                      onClick={() => {
                        void handleResign();
                      }}
                      disabled={actionSubmitting}
                    >
                      Resign
                    </button>
                  </div>
                  {actionError && <p className="error">{actionError}</p>}
                </div>
              )}

              <div className="panel-card">
                <h3>Move History</h3>
                {renderMoveList()}
              </div>
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}
