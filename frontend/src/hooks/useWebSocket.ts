import { useEffect, useRef, useState } from 'react';

export interface WsEvent {
  type: string;
  data: Record<string, unknown>;
}

export function useWebSocket() {
  const [lastEvent, setLastEvent] = useState<WsEvent | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/dashboard`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      setTimeout(() => {
        wsRef.current = new WebSocket(`${protocol}//${window.location.host}/ws/dashboard`);
      }, 3000);
    };
    ws.onmessage = (event) => {
      const parsed = JSON.parse(event.data);
      setLastEvent(parsed);
    };

    return () => ws.close();
  }, []);

  return { lastEvent, connected };
}
