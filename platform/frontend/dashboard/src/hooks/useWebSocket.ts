import { useEffect, useRef, useCallback, useState } from 'react';

export type WSStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface WSEvent {
  type: string;
  customer_id: string;
  payload: Record<string, any>;
  timestamp: string;
}

type EventCallback = (event: WSEvent) => void;

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const WS_URL = API_URL.replace(/^http/, 'ws') + '/api/v1/ws/events';

const RECONNECT_BASE = 1000;
const RECONNECT_MAX = 30000;
const PING_INTERVAL = 25000;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const listenersRef = useRef<Map<string, Set<EventCallback>>>(new Map());
  const globalListenersRef = useRef<Set<EventCallback>>(new Set());
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [status, setStatus] = useState<WSStatus>('disconnected');
  const [lastEvent, setLastEvent] = useState<WSEvent | null>(null);
  const [connectionCount, setConnectionCount] = useState(0);

  const connect = useCallback(() => {
    const token = localStorage.getItem('voxbridge_token');
    if (!token) {
      setStatus('disconnected');
      return;
    }

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    setStatus('connecting');
    const ws = new WebSocket(`${WS_URL}?token=${token}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      reconnectAttemptRef.current = 0;

      // Start ping timer
      if (pingTimerRef.current) clearInterval(pingTimerRef.current);
      pingTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ action: 'ping' }));
        }
      }, PING_INTERVAL);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'pong') return;

        if (data.type === 'connected') {
          setConnectionCount(data.connections || 1);
          return;
        }

        if (data.type === 'catchup' && Array.isArray(data.events)) {
          data.events.forEach((evt: WSEvent) => {
            dispatchEvent(evt);
          });
          return;
        }

        // Regular event
        const wsEvent = data as WSEvent;
        setLastEvent(wsEvent);
        dispatchEvent(wsEvent);
      } catch {}
    };

    ws.onclose = () => {
      setStatus('disconnected');
      if (pingTimerRef.current) clearInterval(pingTimerRef.current);
      scheduleReconnect();
    };

    ws.onerror = () => {
      setStatus('error');
    };
  }, []);

  const dispatchEvent = (event: WSEvent) => {
    // Notify type-specific listeners
    const typeListeners = listenersRef.current.get(event.type);
    if (typeListeners) {
      typeListeners.forEach((cb) => cb(event));
    }

    // Notify global (all events) listeners
    globalListenersRef.current.forEach((cb) => cb(event));
  };

  const scheduleReconnect = useCallback(() => {
    const token = localStorage.getItem('voxbridge_token');
    if (!token) return;

    const delay = Math.min(
      RECONNECT_BASE * Math.pow(2, reconnectAttemptRef.current),
      RECONNECT_MAX
    );
    reconnectAttemptRef.current += 1;

    reconnectTimerRef.current = setTimeout(() => {
      connect();
    }, delay);
  }, [connect]);

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    if (pingTimerRef.current) clearInterval(pingTimerRef.current);
    reconnectAttemptRef.current = 999; // prevent auto-reconnect
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus('disconnected');
  }, []);

  const subscribe = useCallback((eventType: string, callback: EventCallback) => {
    if (!listenersRef.current.has(eventType)) {
      listenersRef.current.set(eventType, new Set());
    }
    listenersRef.current.get(eventType)!.add(callback);
  }, []);

  const unsubscribe = useCallback((eventType: string, callback: EventCallback) => {
    listenersRef.current.get(eventType)?.delete(callback);
  }, []);

  const subscribeAll = useCallback((callback: EventCallback) => {
    globalListenersRef.current.add(callback);
  }, []);

  const unsubscribeAll = useCallback((callback: EventCallback) => {
    globalListenersRef.current.delete(callback);
  }, []);

  // Auto-connect on mount, disconnect on unmount
  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    status,
    lastEvent,
    connectionCount,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    subscribeAll,
    unsubscribeAll,
  };
}
