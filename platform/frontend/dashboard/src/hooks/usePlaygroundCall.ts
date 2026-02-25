import { useState, useRef, useCallback, useEffect } from 'react';

export type CallStatus = 'idle' | 'connecting' | 'listening' | 'processing' | 'speaking' | 'ended' | 'error';

export interface CallTranscript {
  role: 'user' | 'assistant';
  text: string;
  isFinal: boolean;
  sttMs?: number;
  llmMs?: number;
  ttsMs?: number;
  tokensUsed?: number;
}

interface UsePlaygroundCallReturn {
  status: CallStatus;
  transcripts: CallTranscript[];
  currentInterim: string;
  startCall: (sessionId: string) => void;
  endCall: () => void;
  error: string | null;
  latency: { stt: number; llm: number; tts: number };
}

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const WS_BASE = process.env.REACT_APP_WS_URL || API_URL.replace(/^http/, 'ws');

/**
 * Hook for live voice calls in the playground.
 * Opens a WebSocket + mic stream for continuous conversation.
 */
export function usePlaygroundCall(): UsePlaygroundCallReturn {
  const [status, setStatus] = useState<CallStatus>('idle');
  const [transcripts, setTranscripts] = useState<CallTranscript[]>([]);
  const [currentInterim, setCurrentInterim] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [latency, setLatency] = useState({ stt: 0, llm: 0, tts: 0 });

  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const audioQueueRef = useRef<HTMLAudioElement[]>([]);
  const playingRef = useRef(false);

  // Play audio queue sequentially
  const playNextAudio = useCallback(() => {
    if (playingRef.current || audioQueueRef.current.length === 0) return;
    playingRef.current = true;
    const audio = audioQueueRef.current.shift()!;
    audio.onended = () => {
      playingRef.current = false;
      playNextAudio();
    };
    audio.onerror = () => {
      playingRef.current = false;
      playNextAudio();
    };
    audio.play().catch(() => {
      playingRef.current = false;
      playNextAudio();
    });
  }, []);

  const queueAudio = useCallback((base64: string, contentType: string) => {
    if (!base64) return;
    const bytes = atob(base64);
    const arr = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
    const blob = new Blob([arr], { type: contentType });
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.onended = () => URL.revokeObjectURL(url);
    audioQueueRef.current.push(audio);
    playNextAudio();
  }, [playNextAudio]);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'status':
          setStatus(data.status as CallStatus);
          break;

        case 'transcript':
          if (data.is_final) {
            setTranscripts(prev => [...prev, {
              role: 'user',
              text: data.text,
              isFinal: true,
            }]);
            setCurrentInterim('');
          } else {
            setCurrentInterim(data.text);
          }
          break;

        case 'agent_reply':
          setTranscripts(prev => [...prev, {
            role: 'assistant',
            text: data.text,
            isFinal: true,
            sttMs: data.stt_ms,
            llmMs: data.llm_ms,
            ttsMs: data.tts_ms,
            tokensUsed: data.tokens_used,
          }]);
          setLatency({
            stt: data.stt_ms || 0,
            llm: data.llm_ms || 0,
            tts: data.tts_ms || 0,
          });
          if (data.audio_base64) {
            queueAudio(data.audio_base64, data.audio_content_type || 'audio/mpeg');
          }
          break;

        case 'call_ended':
          setStatus('ended');
          break;

        case 'error':
          setError(data.message);
          break;
      }
    } catch {}
  }, [queueAudio]);

  const startCall = useCallback(async (sessionId: string) => {
    setError(null);
    setTranscripts([]);
    setCurrentInterim('');
    setStatus('connecting');
    audioQueueRef.current = [];
    playingRef.current = false;

    const token = localStorage.getItem('voxbridge_token');
    if (!token) {
      setError('Not authenticated');
      setStatus('error');
      return;
    }

    // 1. Get mic access
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
        },
      });
      streamRef.current = stream;
    } catch (err: any) {
      const msg = err.name === 'NotAllowedError'
        ? 'Microphone permission denied'
        : 'Microphone not available';
      setError(msg);
      setStatus('error');
      return;
    }

    // 2. Connect WebSocket
    const wsUrl = `${WS_BASE}/api/v1/playground/ws/call?token=${token}&session_id=${sessionId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('listening');

      // 3. Start streaming mic audio
      const stream = streamRef.current!;
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';

      const recorder = new MediaRecorder(stream, { mimeType });
      recorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
          ws.send(e.data);
        }
      };

      // Send chunks every 250ms for real-time feel
      recorder.start(250);
    };

    ws.onmessage = handleMessage;

    ws.onerror = () => {
      setError('WebSocket connection failed');
      setStatus('error');
    };

    ws.onclose = () => {
      if (status !== 'ended' && status !== 'error') {
        setStatus('ended');
      }
      // Cleanup mic
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.stop();
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
        streamRef.current = null;
      }
    };
  }, [handleMessage, status]);

  const endCall = useCallback(() => {
    // Send end signal
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'end_call' }));
    }

    // Stop recorder
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop();
    }

    // Stop mic
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }

    // Stop all audio
    audioQueueRef.current.forEach(a => { a.pause(); a.src = ''; });
    audioQueueRef.current = [];
    playingRef.current = false;

    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setStatus('ended');
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.stop();
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return {
    status,
    transcripts,
    currentInterim,
    startCall,
    endCall,
    error,
    latency,
  };
}
