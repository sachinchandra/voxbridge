import React, { useState, useEffect, useRef } from 'react';
import { agentAssistApi } from '../services/api';
import { AssistSessionItem, AssistSessionDetail, AssistSuggestion, AssistSummaryData } from '../types';

const SUGGESTION_COLORS: Record<string, { bg: string; text: string; icon: string }> = {
  response: { bg: 'bg-blue-900/30', text: 'text-blue-400', icon: 'Reply' },
  knowledge: { bg: 'bg-purple-900/30', text: 'text-purple-400', icon: 'KB' },
  compliance: { bg: 'bg-red-900/30', text: 'text-red-400', icon: 'Warn' },
  action: { bg: 'bg-amber-900/30', text: 'text-amber-400', icon: 'Act' },
  sentiment: { bg: 'bg-orange-900/30', text: 'text-orange-400', icon: 'Mood' },
};

export default function AgentAssist() {
  const [sessions, setSessions] = useState<AssistSessionItem[]>([]);
  const [summary, setSummary] = useState<AssistSummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedSession, setSelectedSession] = useState<AssistSessionDetail | null>(null);
  const [tab, setTab] = useState<'sessions' | 'demo'>('sessions');

  // Demo state
  const [demoSessionId, setDemoSessionId] = useState('');
  const [demoInput, setDemoInput] = useState('');
  const [demoRole, setDemoRole] = useState<'caller' | 'agent'>('caller');
  const [demoSuggestions, setDemoSuggestions] = useState<AssistSuggestion[]>([]);
  const [demoTranscript, setDemoTranscript] = useState<Array<{ role: string; content: string }>>([]);
  const [demoSentiment, setDemoSentiment] = useState('neutral');
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  const fetchData = async () => {
    try {
      const [s, sum] = await Promise.all([agentAssistApi.listSessions(), agentAssistApi.getSummary()]);
      setSessions(s);
      setSummary(sum);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const viewSession = async (sessionId: string) => {
    try {
      const detail = await agentAssistApi.getSession(sessionId);
      setSelectedSession(detail);
    } catch {}
  };

  // Demo functions
  const startDemo = async () => {
    try {
      const session = await agentAssistApi.startSession({ human_agent_name: 'Demo Agent', call_id: 'demo-call' });
      setDemoSessionId(session.id);
      setDemoSuggestions([]);
      setDemoTranscript([]);
      setDemoSentiment('neutral');
    } catch {}
  };

  const sendDemoMessage = async () => {
    if (!demoSessionId || !demoInput.trim()) return;
    const msg = demoInput.trim();
    setDemoInput('');
    setDemoTranscript(prev => [...prev, { role: demoRole, content: msg }]);

    try {
      const result = await agentAssistApi.addTranscript(demoSessionId, demoRole, msg);
      setDemoSuggestions(prev => [...prev, ...result.suggestions]);
      setDemoSentiment(result.caller_sentiment);
    } catch {}

    setTimeout(() => transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
  };

  const endDemo = async () => {
    if (!demoSessionId) return;
    try {
      const result = await agentAssistApi.endSession(demoSessionId);
      setSelectedSession({ ...result, transcript: demoTranscript, suggestions: demoSuggestions } as any);
      setDemoSessionId('');
      setTab('sessions');
      fetchData();
    } catch {}
  };

  const handleAccept = async (suggestionId: string) => {
    if (!demoSessionId) return;
    try {
      await agentAssistApi.acceptSuggestion(demoSessionId, suggestionId);
      setDemoSuggestions(prev => prev.map(s => s.id === suggestionId ? { ...s, accepted: true } : s));
    } catch {}
  };

  const handleDismiss = async (suggestionId: string) => {
    if (!demoSessionId) return;
    try {
      await agentAssistApi.dismissSuggestion(demoSessionId, suggestionId);
      setDemoSuggestions(prev => prev.map(s => s.id === suggestionId ? { ...s, accepted: false } : s));
    } catch {}
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin w-8 h-8 border-2 border-vox-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Agent Assist</h1>
          <p className="text-sm text-gray-400 mt-1">AI co-pilot for human agents — real-time suggestions during live calls</p>
        </div>
      </div>

      {/* KPIs */}
      {summary && (
        <div className="grid grid-cols-5 gap-4 mb-6">
          {[
            { label: 'Total Sessions', value: summary.total_sessions, color: 'text-white' },
            { label: 'Active Now', value: summary.active_sessions, color: 'text-green-400' },
            { label: 'Suggestions', value: summary.total_suggestions, color: 'text-vox-400' },
            { label: 'Acceptance Rate', value: `${(summary.acceptance_rate * 100).toFixed(0)}%`, color: summary.acceptance_rate > 0.5 ? 'text-green-400' : 'text-amber-400' },
            { label: 'Compliance Warns', value: summary.compliance_warnings, color: summary.compliance_warnings > 0 ? 'text-red-400' : 'text-gray-400' },
          ].map(kpi => (
            <div key={kpi.label} className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-4 text-center">
              <p className="text-xs text-gray-500 uppercase tracking-wider">{kpi.label}</p>
              <p className={`text-2xl font-bold mt-1 ${kpi.color}`}>{kpi.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6">
        {(['sessions', 'demo'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors capitalize ${tab === t ? 'bg-vox-600/20 text-vox-300' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}>
            {t === 'sessions' ? `Sessions (${sessions.length})` : 'Live Demo'}
          </button>
        ))}
      </div>

      {/* Sessions list */}
      {tab === 'sessions' && (
        <div>
          {selectedSession ? (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-white">Session Detail</h3>
                <button onClick={() => setSelectedSession(null)} className="text-xs text-gray-400 hover:text-white transition-colors">Back to list</button>
              </div>
              {selectedSession.call_summary && (
                <div className="bg-[#0f0a1e] rounded-lg p-4 mb-4">
                  <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Call Summary</h4>
                  <p className="text-sm text-gray-300">{selectedSession.call_summary}</p>
                  {selectedSession.next_steps && selectedSession.next_steps.length > 0 && (
                    <div className="mt-3">
                      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Next Steps</h4>
                      <ul className="text-xs text-gray-400 space-y-1">
                        {selectedSession.next_steps.map((step, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <span className="text-vox-400 mt-0.5">-</span> {step}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              <div className="grid grid-cols-4 gap-3 text-xs text-gray-400">
                <div>Sentiment: <span className={selectedSession.caller_sentiment === 'negative' ? 'text-red-400' : 'text-green-400'}>{selectedSession.caller_sentiment}</span></div>
                <div>PII Detected: <span className={selectedSession.pii_detected ? 'text-red-400' : 'text-green-400'}>{selectedSession.pii_detected ? 'Yes' : 'No'}</span></div>
                <div>Accepted: {selectedSession.suggestions_accepted}</div>
                <div>Dismissed: {selectedSession.suggestions_dismissed}</div>
              </div>
            </div>
          ) : (
            <>
              {sessions.length === 0 ? (
                <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-12 text-center">
                  <h2 className="text-lg font-semibold text-white mb-2">No assist sessions yet</h2>
                  <p className="text-sm text-gray-400 mb-4">Start a live demo to see Agent Assist in action.</p>
                  <button onClick={() => setTab('demo')} className="px-6 py-3 bg-vox-600 hover:bg-vox-700 text-white rounded-lg font-medium transition-colors">
                    Try Live Demo
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  {sessions.map(s => (
                    <div key={s.id} onClick={() => viewSession(s.id)} className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-4 cursor-pointer hover:border-vox-700/50 transition-colors">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`w-3 h-3 rounded-full ${s.status === 'active' ? 'bg-green-500 animate-pulse' : 'bg-gray-600'}`} />
                          <div>
                            <p className="text-sm font-medium text-white">{s.human_agent_name || 'Agent'}</p>
                            <div className="flex items-center gap-3 text-xs text-gray-500 mt-1">
                              <span>{s.suggestions_count} suggestions</span>
                              <span>{s.suggestions_accepted} accepted</span>
                              {s.compliance_warnings > 0 && <span className="text-red-400">{s.compliance_warnings} warnings</span>}
                              <span className={s.caller_sentiment === 'negative' ? 'text-red-400' : 'text-gray-500'}>{s.caller_sentiment}</span>
                            </div>
                          </div>
                        </div>
                        <span className="text-xs text-gray-600">{new Date(s.created_at).toLocaleString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Demo tab */}
      {tab === 'demo' && (
        <div>
          {!demoSessionId ? (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-8 text-center">
              <h2 className="text-lg font-semibold text-white mb-2">Agent Assist Live Demo</h2>
              <p className="text-sm text-gray-400 mb-6">Simulate a call between a caller and human agent. Watch AI suggestions appear in real-time.</p>
              <button onClick={startDemo} className="px-6 py-3 bg-vox-600 hover:bg-vox-700 text-white rounded-lg font-medium transition-colors">
                Start Demo Session
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-6">
              {/* Transcript */}
              <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Live Transcript</h3>
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 text-xs rounded-full ${demoSentiment === 'negative' ? 'bg-red-900/30 text-red-400' : demoSentiment === 'positive' ? 'bg-green-900/30 text-green-400' : 'bg-gray-900/30 text-gray-400'}`}>
                      {demoSentiment}
                    </span>
                    <button onClick={endDemo} className="px-3 py-1 text-xs bg-red-900/30 text-red-400 hover:bg-red-900/50 rounded-lg transition-colors">
                      End Call
                    </button>
                  </div>
                </div>

                <div className="h-64 overflow-y-auto space-y-2 mb-4 bg-[#0f0a1e] rounded-lg p-3">
                  {demoTranscript.map((msg, i) => (
                    <div key={i} className={`flex ${msg.role === 'agent' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${msg.role === 'agent' ? 'bg-vox-600/20 text-vox-300' : 'bg-white/5 text-gray-300'}`}>
                        <span className="text-[10px] uppercase text-gray-500 block mb-0.5">{msg.role}</span>
                        {msg.content}
                      </div>
                    </div>
                  ))}
                  <div ref={transcriptEndRef} />
                </div>

                <div className="flex items-center gap-2">
                  <select value={demoRole} onChange={e => setDemoRole(e.target.value as any)} className="px-2 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-xs focus:outline-none">
                    <option value="caller">Caller</option>
                    <option value="agent">Agent</option>
                  </select>
                  <input value={demoInput} onChange={e => setDemoInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendDemoMessage()} placeholder="Type what was said..." className="flex-1 px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500" />
                  <button onClick={sendDemoMessage} className="px-4 py-2 bg-vox-600 hover:bg-vox-700 text-white rounded-lg text-sm font-medium transition-colors">
                    Send
                  </button>
                </div>
              </div>

              {/* Suggestions */}
              <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
                <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">AI Suggestions</h3>
                {demoSuggestions.length === 0 ? (
                  <p className="text-xs text-gray-500">Suggestions will appear here as the call progresses...</p>
                ) : (
                  <div className="space-y-3 max-h-80 overflow-y-auto">
                    {demoSuggestions.slice().reverse().map(s => {
                      const style = SUGGESTION_COLORS[s.type] || SUGGESTION_COLORS.response;
                      return (
                        <div key={s.id} className={`rounded-lg p-3 border border-vox-900/30 ${s.accepted === true ? 'opacity-50' : s.accepted === false ? 'opacity-30' : ''}`}>
                          <div className="flex items-center justify-between mb-1">
                            <span className={`px-2 py-0.5 text-[10px] rounded-full ${style.bg} ${style.text}`}>
                              {style.icon} - {s.type}
                            </span>
                            <span className="text-[10px] text-gray-600">{(s.confidence * 100).toFixed(0)}%</span>
                          </div>
                          <p className="text-sm text-gray-300 mt-1">{s.content}</p>
                          {s.accepted === null && (
                            <div className="flex gap-2 mt-2">
                              <button onClick={() => handleAccept(s.id)} className="px-2 py-1 text-xs bg-green-900/30 text-green-400 hover:bg-green-900/50 rounded transition-colors">
                                Use
                              </button>
                              <button onClick={() => handleDismiss(s.id)} className="px-2 py-1 text-xs bg-gray-800 text-gray-400 hover:bg-gray-700 rounded transition-colors">
                                Dismiss
                              </button>
                            </div>
                          )}
                          {s.accepted === true && <span className="text-[10px] text-green-500 mt-1 block">Accepted</span>}
                          {s.accepted === false && <span className="text-[10px] text-gray-500 mt-1 block">Dismissed</span>}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
