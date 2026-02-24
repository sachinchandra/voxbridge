import React, { useState, useEffect, useRef, useCallback } from 'react';
import { agentsApi, playgroundApi } from '../services/api';
import { AgentListItem, PlaygroundMessage } from '../types';
import { useAudioRecorder } from '../hooks/useAudioRecorder';

type PlaygroundMode = 'text' | 'voice';

export default function Playground() {
  const [agents, setAgents] = useState<AgentListItem[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [agentName, setAgentName] = useState('');
  const [llmInfo, setLlmInfo] = useState('');
  const [messages, setMessages] = useState<PlaygroundMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [totalTokens, setTotalTokens] = useState(0);
  const [totalTurns, setTotalTurns] = useState(0);
  const [sessionActive, setSessionActive] = useState(false);

  // Voice mode state
  const [mode, setMode] = useState<PlaygroundMode>('text');
  const [audioAvailable, setAudioAvailable] = useState(false);
  const [audioProviders, setAudioProviders] = useState({ stt: '', tts: '' });
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [latencyBreakdown, setLatencyBreakdown] = useState({ stt: 0, llm: 0, tts: 0 });

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  const recorder = useAudioRecorder();

  useEffect(() => {
    agentsApi.list().then(setAgents).catch(() => {});
    // Check audio availability
    playgroundApi.audioConfig().then(cfg => {
      setAudioAvailable(cfg.stt_available && cfg.tts_available);
      setAudioProviders({ stt: cfg.stt_provider, tts: cfg.tts_provider });
    }).catch(() => {});
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const startSession = async () => {
    if (!selectedAgentId) return;
    setLoading(true);
    try {
      const res = await playgroundApi.start(selectedAgentId);
      setSessionId(res.session_id);
      setAgentName(res.agent_name);
      setLlmInfo(`${res.llm_provider} / ${res.llm_model}`);
      setSessionActive(true);
      setMessages([]);
      setTotalTokens(0);
      setTotalTurns(0);
      setLatencyBreakdown({ stt: 0, llm: 0, tts: 0 });

      if (res.first_message) {
        setMessages([{
          role: 'assistant',
          content: res.first_message,
          timestamp: Date.now() / 1000,
          latency_ms: 0,
        }]);
        // Auto-speak first message in voice mode
        if (mode === 'voice' && audioAvailable) {
          // Will be spoken when TTS is triggered by the user's first voice message
        }
      }

      setTimeout(() => inputRef.current?.focus(), 100);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to start session');
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || !sessionId || sending) return;
    const userMsg = input.trim();
    setInput('');
    setSending(true);

    setMessages(prev => [...prev, {
      role: 'user',
      content: userMsg,
      timestamp: Date.now() / 1000,
      latency_ms: 0,
    }]);

    try {
      const res = await playgroundApi.sendMessage(sessionId, userMsg);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.reply,
        timestamp: Date.now() / 1000,
        latency_ms: res.latency_ms,
        tool_call: res.tool_calls.length > 0 ? res.tool_calls[0] : undefined,
      }]);
      setTotalTokens(prev => prev + res.tokens_used);
      setTotalTurns(prev => prev + 1);

      if (res.done) {
        setSessionActive(false);
      }
    } catch (err: any) {
      setMessages(prev => [...prev, {
        role: 'system',
        content: `Error: ${err.response?.data?.detail || 'Failed to get response'}`,
        timestamp: Date.now() / 1000,
        latency_ms: 0,
      }]);
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  };

  // ── Voice handling ─────────────────────────────────────────────

  const playAudio = useCallback((base64: string, contentType: string) => {
    if (!base64) return;
    const bytes = atob(base64);
    const arr = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
    const blob = new Blob([arr], { type: contentType });
    const url = URL.createObjectURL(blob);

    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
    }
    const audio = new Audio(url);
    audioPlayerRef.current = audio;
    setAudioPlaying(true);
    audio.onended = () => {
      setAudioPlaying(false);
      URL.revokeObjectURL(url);
    };
    audio.onerror = () => {
      setAudioPlaying(false);
      URL.revokeObjectURL(url);
    };
    audio.play().catch(() => setAudioPlaying(false));
  }, []);

  const handleVoiceToggle = async () => {
    if (recorder.state === 'idle') {
      // Start recording
      await recorder.startRecording();
    } else if (recorder.state === 'recording') {
      // Stop and send
      const blob = await recorder.stopRecording();
      if (!blob || !sessionId) return;

      setSending(true);
      // Show "listening..." placeholder
      setMessages(prev => [...prev, {
        role: 'user',
        content: '🎤 (speaking...)',
        timestamp: Date.now() / 1000,
        latency_ms: 0,
      }]);

      try {
        const res = await playgroundApi.audioTurn(sessionId, blob);

        // Replace the "(speaking...)" placeholder with actual transcript
        setMessages(prev => {
          const updated = [...prev];
          // Find last user message with "(speaking...)"
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'user' && updated[i].content.includes('(speaking...)')) {
              updated[i] = {
                ...updated[i],
                content: res.transcript || '(no speech detected)',
              };
              break;
            }
          }
          return updated;
        });

        if (res.transcript && res.reply) {
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: res.reply,
            timestamp: Date.now() / 1000,
            latency_ms: res.stt_ms + res.llm_ms + res.tts_ms,
            tool_call: res.tool_calls?.length > 0 ? res.tool_calls[0] : undefined,
          }]);
          setTotalTokens(prev => prev + res.tokens_used);
          setTotalTurns(prev => prev + 1);
          setLatencyBreakdown({ stt: res.stt_ms, llm: res.llm_ms, tts: res.tts_ms });

          // Play audio response
          if (res.audio_base64) {
            playAudio(res.audio_base64, res.audio_content_type || 'audio/mpeg');
          }

          if (res.done) {
            setSessionActive(false);
          }
        } else if (res.message) {
          // No speech detected
          setMessages(prev => {
            const updated = [...prev];
            for (let i = updated.length - 1; i >= 0; i--) {
              if (updated[i].role === 'user' && (updated[i].content === '(no speech detected)' || updated[i].content.includes('(speaking...)'))) {
                updated.splice(i, 1);
                break;
              }
            }
            return updated;
          });
        }
      } catch (err: any) {
        const detail = err.response?.data?.detail || err.response?.data?.error || 'Audio processing failed';
        setMessages(prev => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'user' && updated[i].content.includes('(speaking...)')) {
              updated[i] = { ...updated[i], content: '(audio error)' };
              break;
            }
          }
          return [...updated, {
            role: 'system' as const,
            content: `Audio error: ${detail}`,
            timestamp: Date.now() / 1000,
            latency_ms: 0,
          }];
        });
      } finally {
        setSending(false);
      }
    }
  };

  const endSession = async () => {
    if (!sessionId) return;
    recorder.cancelRecording();
    if (audioPlayerRef.current) audioPlayerRef.current.pause();
    try {
      await playgroundApi.endSession(sessionId);
    } catch {}
    setSessionActive(false);
  };

  const resetSession = () => {
    recorder.cancelRecording();
    if (audioPlayerRef.current) audioPlayerRef.current.pause();
    setSessionId(null);
    setMessages([]);
    setAgentName('');
    setLlmInfo('');
    setTotalTokens(0);
    setTotalTurns(0);
    setSessionActive(false);
    setLatencyBreakdown({ stt: 0, llm: 0, tts: 0 });
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Playground</h1>
          <p className="text-sm text-gray-400 mt-1">Test your AI agents via text or voice before deploying</p>
        </div>
        {/* Mode toggle */}
        {audioAvailable && (
          <div className="flex items-center gap-1 bg-[#0f0a1e] rounded-lg p-1 border border-vox-900/50">
            <button
              onClick={() => setMode('text')}
              className={`px-4 py-2 text-xs rounded-md font-medium transition-colors ${
                mode === 'text' ? 'bg-vox-600 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              Text
            </button>
            <button
              onClick={() => setMode('voice')}
              className={`px-4 py-2 text-xs rounded-md font-medium transition-colors flex items-center gap-1.5 ${
                mode === 'voice' ? 'bg-vox-600 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
              Voice
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-4 gap-6" style={{ minHeight: '70vh' }}>
        {/* Chat area */}
        <div className="col-span-3 bg-[#1a1230] rounded-xl border border-vox-900/50 flex flex-col">
          {!sessionId ? (
            /* Agent selector */
            <div className="flex-1 flex items-center justify-center p-8">
              <div className="text-center max-w-md">
                <div className="w-16 h-16 rounded-2xl bg-vox-600/20 flex items-center justify-center mx-auto mb-4">
                  {mode === 'voice' ? (
                    <svg className="w-8 h-8 text-vox-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                    </svg>
                  ) : (
                    <svg className="w-8 h-8 text-vox-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                    </svg>
                  )}
                </div>
                <h2 className="text-lg font-semibold text-white mb-2">
                  {mode === 'voice' ? 'Start a voice conversation' : 'Start a test conversation'}
                </h2>
                <p className="text-sm text-gray-400 mb-6">
                  {mode === 'voice'
                    ? 'Talk to your AI agent using your microphone. Audio goes through the full STT → LLM → TTS pipeline.'
                    : 'Select an AI agent and chat with it to test its responses, tools, and behavior.'}
                </p>
                <select
                  value={selectedAgentId}
                  onChange={(e) => setSelectedAgentId(e.target.value)}
                  className="w-full px-4 py-3 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white mb-4 focus:outline-none focus:ring-2 focus:ring-vox-500"
                >
                  <option value="">Choose an agent...</option>
                  {agents.map(a => (
                    <option key={a.id} value={a.id}>
                      {a.name} ({a.llm_provider}/{a.llm_model})
                    </option>
                  ))}
                </select>
                <button
                  onClick={startSession}
                  disabled={!selectedAgentId || loading}
                  className="w-full px-6 py-3 bg-vox-600 hover:bg-vox-700 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
                >
                  {loading ? 'Starting...' : mode === 'voice' ? 'Start Voice Call' : 'Start Conversation'}
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* Chat header */}
              <div className="px-6 py-4 border-b border-vox-900/50 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    mode === 'voice' ? 'bg-green-600' : 'bg-vox-600'
                  }`}>
                    {mode === 'voice' ? (
                      <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                      </svg>
                    ) : (
                      <span className="text-white text-sm font-bold">{agentName[0]?.toUpperCase()}</span>
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-white">{agentName}</p>
                    <p className="text-xs text-gray-500">{llmInfo}{mode === 'voice' ? ` • Voice mode` : ''}</p>
                  </div>
                  {sessionActive && (
                    <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-green-900/50 text-green-400">Live</span>
                  )}
                  {audioPlaying && (
                    <span className="ml-1 px-2 py-0.5 text-xs rounded-full bg-blue-900/50 text-blue-400 animate-pulse">Speaking</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {sessionActive && (
                    <button
                      onClick={endSession}
                      className="px-3 py-1.5 text-xs bg-red-900/30 text-red-400 hover:bg-red-900/50 rounded-lg transition-colors"
                    >
                      End Call
                    </button>
                  )}
                  <button
                    onClick={resetSession}
                    className="px-3 py-1.5 text-xs bg-white/5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                  >
                    New Test
                  </button>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] ${
                      msg.role === 'user'
                        ? 'bg-vox-600 text-white rounded-2xl rounded-br-md'
                        : msg.role === 'system'
                        ? 'bg-red-900/30 text-red-300 rounded-2xl'
                        : 'bg-[#0f0a1e] text-gray-200 rounded-2xl rounded-bl-md border border-vox-900/30'
                    } px-4 py-3`}>
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                      {msg.tool_call && (
                        <div className="mt-2 px-3 py-2 rounded-lg bg-amber-900/20 border border-amber-800/30">
                          <p className="text-xs text-amber-400 font-mono">
                            Tool: {msg.tool_call.name}({msg.tool_call.arguments})
                          </p>
                        </div>
                      )}
                      {msg.role === 'assistant' && msg.latency_ms > 0 && (
                        <p className="text-[10px] text-gray-500 mt-1">{msg.latency_ms}ms</p>
                      )}
                    </div>
                  </div>
                ))}
                {sending && (
                  <div className="flex justify-start">
                    <div className="bg-[#0f0a1e] border border-vox-900/30 rounded-2xl rounded-bl-md px-4 py-3">
                      <div className="flex gap-1 items-center">
                        <span className="w-2 h-2 bg-vox-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-2 h-2 bg-vox-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-2 h-2 bg-vox-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                        {mode === 'voice' && <span className="ml-2 text-xs text-gray-500">Processing audio...</span>}
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input area */}
              <div className="px-6 py-4 border-t border-vox-900/50">
                {mode === 'voice' && sessionActive ? (
                  /* Voice input */
                  <div className="flex flex-col items-center gap-3">
                    {recorder.error && (
                      <p className="text-xs text-red-400">{recorder.error}</p>
                    )}
                    <div className="flex items-center gap-4">
                      {recorder.state === 'recording' && (
                        <span className="text-sm text-red-400 font-mono animate-pulse">
                          {recorder.duration}s
                        </span>
                      )}
                      <button
                        onClick={handleVoiceToggle}
                        disabled={sending || recorder.state === 'processing'}
                        className={`w-16 h-16 rounded-full flex items-center justify-center transition-all ${
                          recorder.state === 'recording'
                            ? 'bg-red-500 hover:bg-red-600 scale-110 animate-pulse'
                            : sending || recorder.state === 'processing'
                            ? 'bg-gray-700 cursor-not-allowed opacity-50'
                            : 'bg-vox-600 hover:bg-vox-700 hover:scale-105'
                        }`}
                      >
                        {recorder.state === 'recording' ? (
                          /* Stop icon */
                          <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
                            <rect x="6" y="6" width="12" height="12" rx="2" />
                          </svg>
                        ) : sending || recorder.state === 'processing' ? (
                          /* Loading spinner */
                          <svg className="w-6 h-6 text-white animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                        ) : (
                          /* Mic icon */
                          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                          </svg>
                        )}
                      </button>
                      {recorder.state === 'recording' && (
                        <button
                          onClick={recorder.cancelRecording}
                          className="text-xs text-gray-500 hover:text-gray-300"
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                    <p className="text-xs text-gray-500">
                      {recorder.state === 'recording'
                        ? 'Tap to stop and send'
                        : sending
                        ? 'Processing...'
                        : 'Tap to speak'}
                    </p>
                    {/* Also allow text input in voice mode */}
                    <div className="flex gap-3 w-full mt-2">
                      <input
                        ref={inputRef}
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                        placeholder="Or type a message..."
                        disabled={!sessionActive || sending}
                        className="flex-1 px-4 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500 disabled:opacity-50"
                      />
                      <button
                        onClick={sendMessage}
                        disabled={!sessionActive || sending || !input.trim()}
                        className="px-4 py-2 bg-vox-600 hover:bg-vox-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
                      >
                        Send
                      </button>
                    </div>
                  </div>
                ) : (
                  /* Text input */
                  <div className="flex gap-3">
                    <input
                      ref={inputRef}
                      type="text"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                      placeholder={sessionActive ? "Type a message..." : "Session ended"}
                      disabled={!sessionActive || sending}
                      className="flex-1 px-4 py-3 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500 disabled:opacity-50"
                    />
                    <button
                      onClick={sendMessage}
                      disabled={!sessionActive || sending || !input.trim()}
                      className="px-6 py-3 bg-vox-600 hover:bg-vox-700 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
                    >
                      Send
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Sidebar — session info */}
        <div className="space-y-4">
          {/* Stats */}
          <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Session Stats</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-sm text-gray-400">Turns</span>
                <span className="text-sm text-white font-medium">{totalTurns}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-400">Tokens</span>
                <span className="text-sm text-white font-medium">{totalTokens.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-400">Est. Cost</span>
                <span className="text-sm text-white font-medium">${(totalTokens * 0.000003).toFixed(4)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-400">Status</span>
                <span className={`text-sm font-medium ${sessionActive ? 'text-green-400' : sessionId ? 'text-gray-500' : 'text-gray-600'}`}>
                  {sessionActive ? 'Active' : sessionId ? 'Ended' : 'No session'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-400">Mode</span>
                <span className="text-sm text-white font-medium capitalize">{mode}</span>
              </div>
            </div>
          </div>

          {/* Voice latency breakdown */}
          {mode === 'voice' && (latencyBreakdown.stt > 0 || latencyBreakdown.llm > 0) && (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
              <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Latency</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">STT</span>
                  <span className="text-sm text-cyan-400 font-mono">{latencyBreakdown.stt}ms</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">LLM</span>
                  <span className="text-sm text-violet-400 font-mono">{latencyBreakdown.llm}ms</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">TTS</span>
                  <span className="text-sm text-amber-400 font-mono">{latencyBreakdown.tts}ms</span>
                </div>
                <div className="flex justify-between border-t border-vox-900/30 pt-2">
                  <span className="text-sm text-gray-400">Total</span>
                  <span className="text-sm text-white font-mono font-bold">
                    {latencyBreakdown.stt + latencyBreakdown.llm + latencyBreakdown.tts}ms
                  </span>
                </div>
                {audioProviders.stt && (
                  <div className="text-[10px] text-gray-600 mt-1">
                    STT: {audioProviders.stt} • TTS: {audioProviders.tts}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tips */}
          <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Tips</h3>
            <ul className="space-y-2 text-xs text-gray-400">
              {mode === 'voice' ? (
                <>
                  <li className="flex gap-2">
                    <span className="text-vox-400 mt-0.5">&#8226;</span>
                    Click the mic button, speak, then click again to send
                  </li>
                  <li className="flex gap-2">
                    <span className="text-vox-400 mt-0.5">&#8226;</span>
                    Audio goes through STT → LLM → TTS — same pipeline as phone calls
                  </li>
                  <li className="flex gap-2">
                    <span className="text-vox-400 mt-0.5">&#8226;</span>
                    You can also type messages while in voice mode
                  </li>
                  <li className="flex gap-2">
                    <span className="text-vox-400 mt-0.5">&#8226;</span>
                    Latency breakdown shows STT, LLM, and TTS times
                  </li>
                </>
              ) : (
                <>
                  <li className="flex gap-2">
                    <span className="text-vox-400 mt-0.5">&#8226;</span>
                    Test different conversation scenarios
                  </li>
                  <li className="flex gap-2">
                    <span className="text-vox-400 mt-0.5">&#8226;</span>
                    Try asking to speak to a human to test escalation
                  </li>
                  <li className="flex gap-2">
                    <span className="text-vox-400 mt-0.5">&#8226;</span>
                    If agent has tools, try triggering them
                  </li>
                  <li className="flex gap-2">
                    <span className="text-vox-400 mt-0.5">&#8226;</span>
                    End-call phrases auto-end the session
                  </li>
                </>
              )}
              <li className="flex gap-2">
                <span className="text-vox-400 mt-0.5">&#8226;</span>
                Max 50 turns per session
              </li>
            </ul>
          </div>

          {/* Quick actions (text mode only) */}
          {mode === 'text' && (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
              <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Quick Phrases</h3>
              <div className="space-y-2">
                {[
                  'Hello, I need help',
                  "What's my order status?",
                  'I want to speak to a manager',
                  "I'd like to schedule an appointment",
                  'I want a refund',
                ].map((phrase) => (
                  <button
                    key={phrase}
                    onClick={() => {
                      if (sessionActive) {
                        setInput(phrase);
                        setTimeout(() => inputRef.current?.focus(), 50);
                      }
                    }}
                    disabled={!sessionActive}
                    className="w-full text-left px-3 py-2 text-xs text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors disabled:opacity-30"
                  >
                    "{phrase}"
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
