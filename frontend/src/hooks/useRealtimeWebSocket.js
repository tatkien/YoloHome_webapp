import { useEffect, useRef } from 'react';

/** Must stay below server `WS_IDLE_TIMEOUT_SECONDS` (60s) in `backend/app/api/routes/ws.py`. */
const WS_PING_INTERVAL_MS = 30_000;
const WS_RECONNECT_DELAY_MS = 3_000;

function buildWebSocketUrl(token) {
  const base = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  let u;
  try {
    u = new URL(base);
  } catch {
    return null;
  }
  const wsProto = u.protocol === 'https:' ? 'wss' : 'ws';
  return `${wsProto}://${u.host}/api/v1/ws?token=${encodeURIComponent(token)}`;
}

/**
 * Opens the global realtime WebSocket when `token` is set and sends periodic JSON pings
 * so the server does not close the connection on idle timeout.
 */
export function useRealtimeWebSocket(token) {
  const tokenRef = useRef(token);
  tokenRef.current = token;

  useEffect(() => {
    if (!token) return undefined;

    let ws = null;
    let pingTimer = null;
    let reconnectTimer = null;
    let stopped = false;

    const clearTimers = () => {
      if (pingTimer != null) {
        clearInterval(pingTimer);
        pingTimer = null;
      }
      if (reconnectTimer != null) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    const sendPing = () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    };

    const connect = () => {
      if (stopped) return;
      if (!tokenRef.current) return;
      clearTimers();

      const url = buildWebSocketUrl(tokenRef.current);
      if (!url) return;

      ws = new WebSocket(url);

      ws.onopen = () => {
        if (stopped) return;
        sendPing();
        pingTimer = setInterval(sendPing, WS_PING_INTERVAL_MS);
      };

      ws.onmessage = (event) => {
        if (stopped) return;
        try {
          const data = JSON.parse(event.data);
          window.dispatchEvent(new CustomEvent('yolohome:ws', { detail: data }));
        } catch (e) {
          // ignore
        }
      };

      ws.onclose = () => {
        clearTimers();
        if (stopped) return;
        if (!tokenRef.current) return;
        reconnectTimer = setTimeout(connect, WS_RECONNECT_DELAY_MS);
      };

      ws.onerror = () => {
        try {
          ws?.close();
        } catch {
          /* ignore */
        }
      };
    };

    connect();

    return () => {
      stopped = true;
      clearTimers();
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        ws.close();
      }
    };
  }, [token]);
}
