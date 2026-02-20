import React, { useState, useEffect, useRef } from 'react';
import { agentsApi, playgroundApi } from '../services/api';
import { AgentListItem, PlaygroundMessage } from '../types';

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

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    agentsApi.list().then(setAgents).catch(() => {});
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

      if (res.first_message) {
        setMessages([{
          role: 'assistant',
          content: res.first_message,
          timestamp: Date.now() / 1000,
          latency_ms: 0,
        }]);
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

  const endSession = async () => {
    if (!sessionId) return;
    try {
      await playgroundApi.endSession(sessionId);
    } catch {}
    setSessionActive(false);
  };

  const resetSession = () => {
    setSessionId(null);
    setMessages([]);
    setAgentName('');
    setLlmInfo('');
    setTotalTokens(0);
    setTotalTurns(0);
    setSessionActive(false);
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Playground</h1>
          <p className="text-sm text-gray-400 mt-1">Test your AI agents before deploying to phone lines</p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-6" style={{ minHeight: '70vh' }}>
        {/* Chat area */}
        <div className="col-span-3 bg-[#1a1230] rounded-xl border border-vox-900/50 flex flex-col">
          {!sessionId ? (
            /* Agent selector */
            <div className="flex-1 flex items-center justify-center p-8">
              <div className="text-center max-w-md">
                <div className="w-16 h-16 rounded-2xl bg-vox-600/20 flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-vox-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-white mb-2">Start a test conversation</h2>
                <p className="text-sm text-gray-400 mb-6">
                  Select an AI agent and chat with it to test its responses, tools, and behavior.
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
                  {loading ? 'Starting...' : 'Start Conversation'}
                </button>
              </div>
            </div>
          ) : (
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
                      <div className="flex gap-1">
                        <span className="w-2 h-2 bg-vox-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-2 h-2 bg-vox-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-2 h-2 bg-vox-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
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
            </div>
          </div>

          {/* Tips */}
          <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Tips</h3>
            <ul className="space-y-2 text-xs text-gray-400">
              <li className="flex gap-2">
                <span className="text-vox-400 mt-0.5">&#8226;</span>
                Test different conversation scenarios to see how your agent handles them
              </li>
              <li className="flex gap-2">
                <span className="text-vox-400 mt-0.5">&#8226;</span>
                Try asking to speak to a human to test escalation detection
              </li>
              <li className="flex gap-2">
                <span className="text-vox-400 mt-0.5">&#8226;</span>
                If the agent has tools configured, try triggering them (e.g., "check my order status")
              </li>
              <li className="flex gap-2">
                <span className="text-vox-400 mt-0.5">&#8226;</span>
                End-call phrases from your config will auto-end the session
              </li>
              <li className="flex gap-2">
                <span className="text-vox-400 mt-0.5">&#8226;</span>
                Max 50 turns per session — start a new test for fresh context
              </li>
            </ul>
          </div>

          {/* Quick actions */}
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
        </div>
      </div>
    </div>
  );
}
