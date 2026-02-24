import { useState, useRef, useCallback } from 'react';

export type RecordingState = 'idle' | 'recording' | 'processing';

interface UseAudioRecorderReturn {
  state: RecordingState;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<Blob | null>;
  cancelRecording: () => void;
  error: string | null;
  duration: number; // seconds elapsed while recording
}

/**
 * Custom hook for browser microphone recording.
 * Uses MediaRecorder API to capture audio as webm/opus.
 */
export function useAudioRecorder(): UseAudioRecorderReturn {
  const [state, setState] = useState<RecordingState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [duration, setDuration] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const resolveRef = useRef<((blob: Blob | null) => void) | null>(null);

  const cleanup = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    mediaRecorderRef.current = null;
    chunksRef.current = [];
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);
    setDuration(0);
    chunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
        },
      });
      streamRef.current = stream;

      // Pick supported mime type
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : 'audio/mp4';

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      recorder.start(100); // collect data every 100ms
      setState('recording');

      // Duration timer
      const startTime = Date.now();
      timerRef.current = setInterval(() => {
        setDuration(Math.floor((Date.now() - startTime) / 1000));
      }, 200);
    } catch (err: any) {
      const msg = err.name === 'NotAllowedError'
        ? 'Microphone permission denied. Please allow mic access.'
        : err.name === 'NotFoundError'
        ? 'No microphone found. Please connect a microphone.'
        : `Microphone error: ${err.message}`;
      setError(msg);
      cleanup();
    }
  }, [cleanup]);

  const stopRecording = useCallback(async (): Promise<Blob | null> => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === 'inactive') {
      cleanup();
      setState('idle');
      return null;
    }

    return new Promise<Blob | null>((resolve) => {
      resolveRef.current = resolve;

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
        cleanup();
        setState('processing');
        resolve(blob);
      };

      recorder.stop();
    });
  }, [cleanup]);

  const cancelRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop();
    }
    cleanup();
    setState('idle');
    if (resolveRef.current) {
      resolveRef.current(null);
      resolveRef.current = null;
    }
  }, [cleanup]);

  return {
    state,
    startRecording,
    stopRecording,
    cancelRecording,
    error,
    duration,
  };
}
