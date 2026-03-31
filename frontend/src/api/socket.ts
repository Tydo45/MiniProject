import type { LobbySocketMessage } from "../types/lobby";

const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const LOBBY_WS_URL = `${protocol}//${window.location.host}/api/lobby/ws`;

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
