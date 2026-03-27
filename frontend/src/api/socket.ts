import type { LobbySocketMessage } from "../types/lobby";

const LOBBY_WS_URL = "ws://localhost:8001/ws";

type SocketHandlers = {
  onClose?: () => void;
  onError?: () => void;
  onMessage: (message: LobbySocketMessage) => void;
  onOpen?: () => void;
};

export function connectLobbySocket(
  accessToken: string,
  handlers: SocketHandlers,
): WebSocket {
  const socket = new WebSocket(
    `${LOBBY_WS_URL}?token=${encodeURIComponent(accessToken)}`,
  );

  socket.onopen = () => {
    handlers.onOpen?.();
  };

  socket.onclose = () => {
    handlers.onClose?.();
  };

  socket.onerror = () => {
    handlers.onError?.();
  };

  socket.onmessage = (event) => {
    try {
      handlers.onMessage(JSON.parse(event.data) as LobbySocketMessage);
    } catch {
      // Ignore malformed frames.
    }
  };

  return socket;
}
