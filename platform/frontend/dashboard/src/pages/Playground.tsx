import React, { useState, useEffect, useRef } from 'react';
import { agentsApi, playgroundApi } from '../services/api';
import { AgentListItem, PlaygroundMessage } from '../types';
import { usePlaygroundCall, CallStatus } from '../hooks/usePlaygroundCall';

type PlaygroundMode = 'text' | 'voice';

// Pulse animation for the call button
const pulseKeyframes = `
@keyframes call-pulse {
  0% { box-shadow: 0 0 0 0 rgba(34,197,94,0.5); }
  70% { box-shadow: 0 0 0 15px rgba(34,197,94,0); }
  100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); }
}
@keyframes waveform {
  0%, 100% { height: 4px; }
  50% { height: 20px; }
}
`;

function StatusIndicator({ status }: { status: CallStatus }) {
  const config: Record<CallStatus, { color: string; label: string; animate: boolean }> = {
    idle: { color: 'bg-gray-500', label: 'Ready', animate: false },
    connecting: { color: 'bg-yellow-500', label: 'Connecting...', animate: true },
    listening: { color: 'bg-green-500', label: 'Listening', animate: true },
    processing: { color: 'bg-violet-500', label: 'Thinking...', animate: true },
    speaking: { color: 'bg-blue-500', label: 'Speaking', animate: true },
    ended: { color: 'bg-gray-500', label: 'Call ended', animate: false },
    error: { color: 'bg-red-500', label: 'Error', animate: false },
  };
  const c = config[status];
  return (
    <div className="flex items-center gap-2">
      <span className={`w-2.5 h-2.5 rounded-full ${c.color} ${c.animate ? 'animate-pulse' : ''}`} />
      <span className="text-xs text-gray-400 font-medium">{c.label}</span>
    </div>
  );
}

function Waveform({ active }: { active: boolean }) {
  if (!active) return null;
  return (
    <div className="flex items-center gap-[3px] h-6">
      {[0, 1, 2, 3, 4].map(i => (
        <div
          key={i}
          className="w-[3px] bg-green-400 rounded-full"
          style={{
            animation: `waveform 0.6s ease-in-out ${i * 0.1}s infinite`,
            height: '4px',
          }}
        />
      ))}
    </div>
  );
}

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

  // Mode toggle
  const [mode, setMode] = useState<PlaygroundMode>('text');
  const [audioAvailable, setAudioAvailable] = useState(false);
  const [audioProviders, setAudioProviders] = useState({ stt: '', tts: '' });

  // Live call hook
  const liveCall = usePlaygroundCall();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    agentsApi.list().then(setAgents).catch(() => {});
    playgroundApi.audioConfig().then(cfg => {
      setAudioAvailable(cfg.stt_available && cfg.tts_available);
      setAudioProviders({ stt: cfg.stt_provider, tts: cfg.tts_provider });
    }).catch(() => {});
  }, []);

  // Auto-scroll when messages or live transcripts change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, liveCall.transcripts, liveCall.currentInterim]);

  // Sync live call transcripts to token/turn counters
  useEffect(() => {
    const assistantMsgs = liveCall.transcripts.filter(t => t.role === 'assistant');
    const tokens = assistantMsgs.reduce((sum, t) => sum + (t.tokensUsed || 0), 0);
    const turns = assistantMsgs.length;
    setTotalTokens(tokens);
    setTotalTurns(turns);
  }, [liveCall.transcripts]);

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

      if (mode === 'voice') {
        // In voice mode, start the live call immediately
        liveCall.startCall(res.session_id);
        // Show first message if available
        if (res.first_message) {
          setMessages([{
            role: 'assistant',
            content: res.first_message,
            timestamp: Date.now() / 1000,
            latency_ms: 0,
          }]);
        }
      } else {
        if (res.first_message) {
          setMessages([{
            role: 'assistant',
            content: res.first_message,
            timestamp: Date.now() / 1000,
            latency_ms: 0,
          }]);
        }
        setTimeout(() => inputRef.current?.focus(), 100);
      }
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

  const endSession = async () => {
    if (mode === 'voice') {
      liveCall.endCall();
    }
    if (sessionId) {
      try {
        await playgroundApi.endSession(sessionId);
      } catch {}
    }
    setSessionActive(false);
  };

  const resetSession = () => {
    if (mode === 'voice' && liveCall.status !== 'idle' && liveCall.status !== 'ended') {
      liveCall.endCall();
    }
    setSessionId(null);
    setMessages([]);
    setAgentName('');
    setLlmInfo('');
    setTotalTokens(0);
    setTotalTurns(0);
    setSessionActive(false);
  };

  const isCallActive = mode === 'voice' && sessionActive &&
    !['idle', 'ended', 'error'].includes(liveCall.status);

  // Combine text messages with live call transcripts for voice mode
  const renderVoiceTranscripts = () => {
    const items: React.ReactNode[] = [];

    // Show initial messages (like first_message)
    messages.forEach((msg, i) => {
      items.push(
        <div key={`msg-${i}`} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          <div className={`max-w-[80%] ${
            msg.role === 'user'
              ? 'bg-vox-600 text-white rounded-2xl rounded-br-md'
              : msg.role === 'system'
              ? 'bg-red-900/30 text-red-300 rounded-2xl'
              : 'bg-[#0f0a1e] text-gray-200 rounded-2xl rounded-bl-md border border-vox-900/30'
          } px-4 py-3`}>
            <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
          </div>
        </div>
      );
    });

    // Show live call transcripts
    liveCall.transcripts.forEach((t, i) => {
      items.push(
        <div key={`live-${i}`} className={`flex ${t.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          <div className={`max-w-[80%] ${
            t.role === 'user'
              ? 'bg-vox-600 text-white rounded-2xl rounded-br-md'
              : 'bg-[#0f0a1e] text-gray-200 rounded-2xl rounded-bl-md border border-vox-900/30'
          } px-4 py-3`}>
            <p className="text-sm whitespace-pre-wrap">{t.text}</p>
            {t.role === 'assistant' && (t.sttMs || t.llmMs || t.ttsMs) && (
              <div className="flex gap-2 mt-1.5">
                {t.sttMs != null && <span className="text-[10px] text-cyan-500/60">STT {t.sttMs}ms</span>}
                {t.llmMs != null && <span className="text-[10px] text-violet-500/60">LLM {t.llmMs}ms</span>}
                {t.ttsMs != null && <span className="text-[10px] text-amber-500/60">TTS {t.ttsMs}ms</span>}
              </div>
            )}
          </div>
        </div>
      );
    });

    // Show interim (currently being spoken by user)
    if (liveCall.currentInterim) {
      items.push(
        <div key="interim" className="flex justify-end">
          <div className="max-w-[80%] bg-vox-600/50 text-white/70 rounded-2xl rounded-br-md px-4 py-3 border border-vox-500/30">
            <p className="text-sm italic">{liveCall.currentInterim}</p>
            <p className="text-[10px] text-vox-300/50 mt-0.5">listening...</p>
          </div>
        </div>
      );
    }

    // Show processing indicator
    if (liveCall.status === 'processing') {
      items.push(
        <div key="processing" className="flex justify-start">
          <div className="bg-[#0f0a1e] border border-vox-900/30 rounded-2xl rounded-bl-md px-4 py-3">
            <div className="flex gap-1 items-center">
              <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              <span className="ml-2 text-xs text-gray-500">Thinking...</span>
            </div>
          </div>
        </div>
      );
    }

    return items;
  };

  return (
    <div>
      <style>{pulseKeyframes}</style>

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Playground</h1>
          <p className="text-sm text-gray-400 mt-1">Test your AI agents via text or live voice call</p>
        </div>
        {/* Mode toggle */}
        {audioAvailable && (
          <div className="flex items-center gap-1 bg-[#0f0a1e] rounded-lg p-1 border border-vox-900/50">
            <button
              onClick={() => !sessionId && setMode('text')}
              disabled={!!sessionId}
              className={`px-4 py-2 text-xs rounded-md font-medium transition-colors ${
                mode === 'text' ? 'bg-vox-600 text-white' : 'text-gray-400 hover:text-white'
              } ${sessionId ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              Text
            </button>
            <button
              onClick={() => !sessionId && setMode('voice')}
              disabled={!!sessionId}
              className={`px-4 py-2 text-xs rounded-md font-medium transition-colors flex items-center gap-1.5 ${
                mode === 'voice' ? 'bg-green-600 text-white' : 'text-gray-400 hover:text-white'
              } ${sessionId ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
              </svg>
              Live Call
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-4 gap-6" style={{ minHeight: '70vh' }}>
        {/* Chat / Call area */}
        <div className="col-span-3 bg-[#1a1230] rounded-xl border border-vox-900/50 flex flex-col">
          {!sessionId ? (
            /* Agent selector */
            <div className="flex-1 flex items-center justify-center p-8">
              <div className="text-center max-w-md">
                <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 ${
                  mode === 'voice' ? 'bg-green-600/20' : 'bg-vox-600/20'
                }`}>
                  {mode === 'voice' ? (
                    <svg className="w-8 h-8 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                    </svg>
                  ) : (
                    <svg className="w-8 h-8 text-vox-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                    </svg>
                  )}
                </div>
                <h2 className="text-lg font-semibold text-white mb-2">
                  {mode === 'voice' ? 'Start a live voice call' : 'Start a test conversation'}
                </h2>
                <p className="text-sm text-gray-400 mb-6">
                  {mode === 'voice'
                    ? 'Have a real-time conversation with your AI agent. Speak naturally — the agent will listen, think, and respond just like a phone call.'
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
                  className={`w-full px-6 py-3 text-white rounded-lg font-medium transition-colors disabled:opacity-50 ${
                    mode === 'voice'
                      ? 'bg-green-600 hover:bg-green-700'
                      : 'bg-vox-600 hover:bg-vox-700'
                  }`}
                >
                  {loading ? 'Connecting...' : mode === 'voice' ? '📞 Start Live Call' : 'Start Conversation'}
                </button>
              </div>
            </div>
          ) : mode === 'voice' ? (
            /* ═══════════ LIVE CALL VIEW ═══════════ */
            <>
              {/* Call header */}
              <div className="px-6 py-4 border-b border-vox-900/50 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    isCallActive ? 'bg-green-600' : 'bg-gray-600'
                  }`}>
                    <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-white">{agentName}</p>
                    <p className="text-xs text-gray-500">{llmInfo} • Live Call</p>
                  </div>
                  <StatusIndicator status={liveCall.status} />
                  <Waveform active={liveCall.status === 'listening' || liveCall.status === 'speaking'} />
                </div>
                <div className="flex items-center gap-2">
                  {isCallActive && (
                    <button
                      onClick={endSession}
                      className="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-full font-medium transition-colors flex items-center gap-2"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 8l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M5 3a2 2 0 00-2 2v1c0 8.284 6.716 15 15 15h1a2 2 0 002-2v-3.28a1 1 0 00-.684-.948l-4.493-1.498a1 1 0 00-1.21.502l-1.13 2.257a11.042 11.042 0 01-5.516-5.516l2.257-1.13a1 1 0 00.502-1.21L8.228 3.684A1 1 0 007.28 3H5z" />
                      </svg>
                      End Call
                    </button>
                  )}
                  {!isCallActive && (
                    <button
                      onClick={resetSession}
                      className="px-3 py-1.5 text-xs bg-white/5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                    >
                      New Call
                    </button>
                  )}
                </div>
              </div>

              {/* Live transcript area */}
              <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {liveCall.error && (
                  <div className="flex justify-center">
                    <div className="bg-red-900/30 text-red-300 rounded-xl px-4 py-3 text-sm max-w-md text-center">
                      {liveCall.error}
                    </div>
                  </div>
                )}

                {liveCall.status === 'connecting' && (
                  <div className="flex-1 flex items-center justify-center">
                    <div className="text-center">
                      <div className="w-12 h-12 border-4 border-green-500/30 border-t-green-500 rounded-full animate-spin mx-auto mb-3" />
                      <p className="text-sm text-gray-400">Connecting to agent...</p>
                      <p className="text-xs text-gray-600 mt-1">Setting up microphone and audio</p>
                    </div>
                  </div>
                )}

                {renderVoiceTranscripts()}

                {/* Show empty state when call is active but no transcripts yet */}
                {isCallActive && liveCall.transcripts.length === 0 && !liveCall.currentInterim && messages.length <= 1 && liveCall.status !== 'connecting' && (
                  <div className="flex items-center justify-center py-12">
                    <div className="text-center">
                      <div className="w-20 h-20 rounded-full bg-green-600/10 flex items-center justify-center mx-auto mb-4"
                        style={{ animation: 'call-pulse 2s infinite' }}
                      >
                        <svg className="w-10 h-10 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                        </svg>
                      </div>
                      <p className="text-sm text-gray-400">Call is active — start speaking</p>
                      <p className="text-xs text-gray-600 mt-1">The agent will respond in real time</p>
                    </div>
                  </div>
                )}

                {/* Call ended state */}
                {liveCall.status === 'ended' && (
                  <div className="flex justify-center mt-4">
                    <div className="bg-[#0f0a1e] border border-vox-900/30 rounded-xl px-6 py-4 text-center">
                      <p className="text-sm text-gray-400 mb-2">Call ended</p>
                      <p className="text-xs text-gray-600">
                        {liveCall.transcripts.filter(t => t.role === 'assistant').length} agent responses •{' '}
                        {liveCall.transcripts.filter(t => t.role === 'user').length} user messages
                      </p>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Call controls bar */}
              <div className="px-6 py-4 border-t border-vox-900/50">
                {isCallActive ? (
                  <div className="flex items-center justify-center gap-6">
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                      <span className={`w-2 h-2 rounded-full ${
                        liveCall.status === 'listening' ? 'bg-green-400 animate-pulse' : 'bg-gray-600'
                      }`} />
                      <span>Mic active</span>
                    </div>
                    <button
                      onClick={endSession}
                      className="w-14 h-14 rounded-full bg-red-600 hover:bg-red-700 flex items-center justify-center transition-colors shadow-lg shadow-red-900/30"
                    >
                      <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 8l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M5 3a2 2 0 00-2 2v1c0 8.284 6.716 15 15 15h1a2 2 0 002-2v-3.28a1 1 0 00-.684-.948l-4.493-1.498a1 1 0 00-1.21.502l-1.13 2.257a11.042 11.042 0 01-5.516-5.516l2.257-1.13a1 1 0 00.502-1.21L8.228 3.684A1 1 0 007.28 3H5z" />
                      </svg>
                    </button>
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                      <span className={`w-2 h-2 rounded-full ${
                        liveCall.status === 'speaking' ? 'bg-blue-400 animate-pulse' : 'bg-gray-600'
                      }`} />
                      <span>Speaker</span>
                    </div>
                  </div>
                ) : (
                  <div className="flex justify-center">
                    <button
                      onClick={resetSession}
                      className="px-6 py-2 bg-vox-600 hover:bg-vox-700 text-white text-sm rounded-lg font-medium transition-colors"
                    >
                      Start New Call
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            /* ═══════════ TEXT CHAT VIEW ═══════════ */
            <>
              {/* Chat header */}
              <div className="px-6 py-4 border-b border-vox-900/50 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-vox-600 flex items-center justify-center">
                    <span className="text-white text-sm font-bold">{agentName[0]?.toUpperCase()}</span>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-white">{agentName}</p>
                    <p className="text-xs text-gray-500">{llmInfo}</p>
                  </div>
                  {sessionActive && (
                    <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-green-900/50 text-green-400">Live</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {sessionActive && (
                    <button
                      onClick={endSession}
                      className="px-3 py-1.5 text-xs bg-red-900/30 text-red-400 hover:bg-red-900/50 rounded-lg transition-colors"
                    >
                      End
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
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Text input */}
              <div className="px-6 py-4 border-t border-vox-900/50">
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
              </div>
            </>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Stats */}
          <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
              {mode === 'voice' ? 'Call Stats' : 'Session Stats'}
            </h3>
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
                <span className={`text-sm font-medium ${
                  mode === 'voice' && isCallActive
                    ? 'text-green-400'
                    : sessionActive ? 'text-green-400' : sessionId ? 'text-gray-500' : 'text-gray-600'
                }`}>
                  {mode === 'voice'
                    ? isCallActive ? 'On Call' : liveCall.status === 'ended' ? 'Ended' : 'No call'
                    : sessionActive ? 'Active' : sessionId ? 'Ended' : 'No session'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-400">Mode</span>
                <span className={`text-sm font-medium ${mode === 'voice' ? 'text-green-400' : 'text-white'}`}>
                  {mode === 'voice' ? '📞 Live Call' : '💬 Text'}
                </span>
              </div>
            </div>
          </div>

          {/* Voice latency breakdown */}
          {mode === 'voice' && liveCall.latency.stt + liveCall.latency.llm + liveCall.latency.tts > 0 && (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
              <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Last Response</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">STT</span>
                  <span className="text-sm text-cyan-400 font-mono">{liveCall.latency.stt}ms</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">LLM</span>
                  <span className="text-sm text-violet-400 font-mono">{liveCall.latency.llm}ms</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">TTS</span>
                  <span className="text-sm text-amber-400 font-mono">{liveCall.latency.tts}ms</span>
                </div>
                <div className="flex justify-between border-t border-vox-900/30 pt-2">
                  <span className="text-sm text-gray-400">Total</span>
                  <span className="text-sm text-white font-mono font-bold">
                    {liveCall.latency.stt + liveCall.latency.llm + liveCall.latency.tts}ms
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
                    <span className="text-green-400 mt-0.5">&#8226;</span>
                    Just speak naturally — the agent listens continuously
                  </li>
                  <li className="flex gap-2">
                    <span className="text-green-400 mt-0.5">&#8226;</span>
                    The agent will pause to think, then speak its response
                  </li>
                  <li className="flex gap-2">
                    <span className="text-green-400 mt-0.5">&#8226;</span>
                    Real-time STT → LLM → TTS — same pipeline as phone calls
                  </li>
                  <li className="flex gap-2">
                    <span className="text-green-400 mt-0.5">&#8226;</span>
                    Latency breakdown updates after each response
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
