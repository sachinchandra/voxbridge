import React, { createContext, useContext } from 'react';
import { useWebSocket, WSStatus, WSEvent } from '../hooks/useWebSocket';

interface WebSocketContextType {
  status: WSStatus;
  lastEvent: WSEvent | null;
  connectionCount: number;
  subscribe: (eventType: string, callback: (event: WSEvent) => void) => void;
  unsubscribe: (eventType: string, callback: (event: WSEvent) => void) => void;
  subscribeAll: (callback: (event: WSEvent) => void) => void;
  unsubscribeAll: (callback: (event: WSEvent) => void) => void;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const ws = useWebSocket();

  return (
    <WebSocketContext.Provider value={ws}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWS(): WebSocketContextType {
  const ctx = useContext(WebSocketContext);
  if (!ctx) {
    throw new Error('useWS must be used within a WebSocketProvider');
  }
  return ctx;
}
