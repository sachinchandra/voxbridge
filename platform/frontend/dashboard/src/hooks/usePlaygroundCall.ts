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

export interface CallLog {
  ts: number;
  level: 'info' | 'warn' | 'error' | 'audio' | 'ws';
  msg: string;
}

interface UsePlaygroundCallReturn {
  status: CallStatus;
  transcripts: CallTranscript[];
  currentInterim: string;
  startCall: (sessionId: string) => void;
  endCall: () => void;
  error: string | null;
  latency: { stt: number; llm: number; tts: number };
  logs: CallLog[];
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
  const [logs, setLogs] = useState<CallLog[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const audioQueueRef = useRef<HTMLAudioElement[]>([]);
  const playingRef = useRef(false);

  // Logging helper — pushes to state + console
  const log = useCallback((level: CallLog['level'], msg: string) => {
    const entry: CallLog = { ts: Date.now(), level, msg };
    setLogs(prev => [...prev.slice(-200), entry]); // keep last 200
    const prefix = `[VoxCall:${level}]`;
    if (level === 'error') console.error(prefix, msg);
    else if (level === 'warn') console.warn(prefix, msg);
    else console.log(prefix, msg);
  }, []);

  // Play audio queue sequentially
  const playNextAudio = useCallback(() => {
    if (playingRef.current || audioQueueRef.current.length === 0) return;
    playingRef.current = true;
    const audio = audioQueueRef.current.shift()!;
    log('audio', `Playing audio, queue remaining: ${audioQueueRef.current.length}`);
    audio.onended = () => {
      log('audio', 'Playback ended');
      playingRef.current = false;
      playNextAudio();
    };
    audio.onerror = (e) => {
      log('error', `Playback error: ${(e as any)?.message || 'unknown'}`);
      playingRef.current = false;
      playNextAudio();
    };
    audio.play().then(() => {
      log('audio', `play() started OK, duration=${audio.duration}s`);
    }).catch((err) => {
      log('error', `play() rejected: ${err?.message || err}`);
      playingRef.current = false;
      playNextAudio();
    });
  }, [log]);

  const queueAudio = useCallback((base64: string, contentType: string) => {
    if (!base64) {
      log('warn', 'queueAudio called with empty base64');
      return;
    }
    log('audio', `Queueing audio: b64_len=${base64.length}, type=${contentType}`);
    try {
      const raw = atob(base64);
      const arr = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
      const blob = new Blob([arr], { type: contentType });
      log('audio', `Blob created: ${blob.size} bytes`);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => URL.revokeObjectURL(url);
      audioQueueRef.current.push(audio);
      playNextAudio();
    } catch (err: any) {
      log('error', `Failed to decode audio: ${err?.message || err}`);
    }
  }, [playNextAudio, log]);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'status':
          log('ws', `status → ${data.status}`);
          setStatus(data.status as CallStatus);
          break;

        case 'transcript': {
          const label = data.is_final ? 'FINAL' : 'interim';
          log('ws', `transcript (${label}): "${data.text}"`);
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
        }

        case 'agent_reply': {
          const audioLen = data.audio_base64?.length || 0;
          log('ws', `agent_reply: text="${data.text?.slice(0, 60)}..." audio_b64_len=${audioLen} stt=${data.stt_ms}ms llm=${data.llm_ms}ms tts=${data.tts_ms}ms`);
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
          } else {
            log('warn', 'agent_reply has NO audio_base64 — TTS may have failed');
          }
          break;
        }

        case 'call_ended':
          log('ws', 'call_ended received');
          setStatus('ended');
          break;

        case 'error':
          log('error', `Server error: ${data.message}`);
          setError(data.message);
          break;

        default:
          log('ws', `Unknown message type: ${data.type}`);
      }
    } catch (err: any) {
      log('error', `Failed to parse WS message: ${err?.message}`);
    }
  }, [queueAudio, log]);

  const startCall = useCallback(async (sessionId: string) => {
    setError(null);
    setTranscripts([]);
    setCurrentInterim('');
    setLogs([]);
    setStatus('connecting');
    audioQueueRef.current = [];
    playingRef.current = false;

    log('info', `Starting call for session=${sessionId}`);
    log('info', `WS base URL: ${WS_BASE}`);

    const token = localStorage.getItem('voxbridge_token');
    if (!token) {
      log('error', 'No auth token in localStorage');
      setError('Not authenticated');
      setStatus('error');
      return;
    }
    log('info', `Auth token: ${token.slice(0, 20)}...`);

    // 1. Get mic access
    try {
      log('info', 'Requesting microphone access...');
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
        },
      });
      streamRef.current = stream;
      const track = stream.getAudioTracks()[0];
      log('info', `Mic ready: ${track.label}, settings=${JSON.stringify(track.getSettings())}`);
    } catch (err: any) {
      const msg = err.name === 'NotAllowedError'
        ? 'Microphone permission denied'
        : `Microphone error: ${err.message}`;
      log('error', msg);
      setError(msg);
      setStatus('error');
      return;
    }

    // 2. Connect WebSocket
    const wsUrl = `${WS_BASE}/api/v1/playground/ws/call?token=${token}&session_id=${sessionId}`;
    log('info', `Connecting WS: ${wsUrl.replace(token, 'TOKEN')}`);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      log('info', 'WebSocket connected');
      setStatus('listening');

      // 3. Start streaming mic audio
      const stream = streamRef.current!;
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';

      log('info', `MediaRecorder mimeType: ${mimeType}`);
      const recorder = new MediaRecorder(stream, { mimeType });
      recorderRef.current = recorder;

      let chunkCount = 0;
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
          chunkCount++;
          if (chunkCount <= 3 || chunkCount % 20 === 0) {
            log('info', `Mic chunk #${chunkCount}: ${e.data.size} bytes`);
          }
          ws.send(e.data);
        }
      };

      // Send chunks every 250ms for real-time feel
      recorder.start(250);
      log('info', 'MediaRecorder started (250ms chunks)');
    };

    ws.onmessage = handleMessage;

    ws.onerror = (e) => {
      log('error', `WebSocket error: ${JSON.stringify(e)}`);
      setError('WebSocket connection failed');
      setStatus('error');
    };

    ws.onclose = (e) => {
      log('info', `WebSocket closed: code=${e.code} reason=${e.reason}`);
      setStatus((prev) => {
        if (prev !== 'ended' && prev !== 'error') return 'ended';
        return prev;
      });
      // Cleanup mic
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.stop();
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
        streamRef.current = null;
      }
    };
  }, [handleMessage, log]);

  const endCall = useCallback(() => {
    log('info', 'Ending call...');
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
  }, [log]);

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
    logs,
  };
}
