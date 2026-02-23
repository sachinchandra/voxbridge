import React, { useState, useEffect } from 'react';
import { flowsApi, agentsApi } from '../services/api';
import { FlowListItem, ConversationFlow, FlowNode, FlowTestResult, AgentListItem } from '../types';

const NODE_COLORS: Record<string, string> = {
  start: 'bg-green-600',
  message: 'bg-blue-600',
  listen: 'bg-amber-600',
  ai_respond: 'bg-vox-600',
  condition: 'bg-orange-600',
  tool_call: 'bg-cyan-600',
  transfer: 'bg-red-600',
  end: 'bg-gray-600',
};

const NODE_LABELS: Record<string, string> = {
  start: 'Start',
  message: 'Message',
  listen: 'Listen',
  ai_respond: 'AI Respond',
  condition: 'Condition',
  tool_call: 'Tool Call',
  transfer: 'Transfer',
  end: 'End',
};

export default function FlowBuilder() {
  const [flows, setFlows] = useState<FlowListItem[]>([]);
  const [agents, setAgents] = useState<AgentListItem[]>([]);
  const [selectedFlow, setSelectedFlow] = useState<ConversationFlow | null>(null);
  const [testInputs, setTestInputs] = useState('');
  const [testResult, setTestResult] = useState<FlowTestResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [view, setView] = useState<'list' | 'editor'>('list');

  useEffect(() => {
    Promise.all([flowsApi.list(), agentsApi.list()])
      .then(([f, a]) => { setFlows(f); setAgents(a); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const createDefaultFlow = async () => {
    const agentId = agents[0]?.id || '';
    try {
      const flow = await flowsApi.createDefault(agentId, 'My First Flow');
      setSelectedFlow(flow);
      setView('editor');
      setFlows(await flowsApi.list());
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create flow');
    }
  };

  const openFlow = async (flowId: string) => {
    try {
      const flow = await flowsApi.get(flowId);
      setSelectedFlow(flow);
      setView('editor');
    } catch {}
  };

  const activateFlow = async () => {
    if (!selectedFlow) return;
    try {
      await flowsApi.activate(selectedFlow.id);
      setSelectedFlow({ ...selectedFlow, is_active: true });
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (detail?.errors) {
        alert('Validation errors:\n' + detail.errors.join('\n'));
      } else {
        alert(detail || 'Failed to activate');
      }
    }
  };

  const testFlow = async () => {
    if (!selectedFlow) return;
    setTesting(true);
    try {
      const inputs = testInputs.split('\n').filter(l => l.trim());
      const result = await flowsApi.test(selectedFlow.id, inputs);
      setTestResult(result);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Test failed');
    } finally {
      setTesting(false);
    }
  };

  const deleteFlow = async (flowId: string) => {
    try {
      await flowsApi.delete(flowId);
      setFlows(flows.filter(f => f.id !== flowId));
      if (selectedFlow?.id === flowId) {
        setSelectedFlow(null);
        setView('list');
      }
    } catch {}
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin w-8 h-8 border-2 border-vox-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  // ── List view ──────────────────────────────────────────────────
  if (view === 'list') {
    return (
      <div>
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">Conversation Flows</h1>
            <p className="text-sm text-gray-400 mt-1">Visual call flow builder with decision trees and A/B testing</p>
          </div>
          <button onClick={createDefaultFlow} className="px-4 py-2 bg-vox-600 hover:bg-vox-700 text-white rounded-lg text-sm font-medium transition-colors">
            + New Flow
          </button>
        </div>

        {flows.length === 0 ? (
          <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-12 text-center">
            <div className="w-16 h-16 rounded-2xl bg-vox-600/20 flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-vox-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-white mb-2">No flows yet</h2>
            <p className="text-sm text-gray-400 mb-6">Create your first conversation flow to design structured call experiences.</p>
            <button onClick={createDefaultFlow} className="px-6 py-3 bg-vox-600 hover:bg-vox-700 text-white rounded-lg font-medium transition-colors">
              Create Default Flow
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {flows.map(flow => (
              <div key={flow.id} className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5 hover:border-vox-700/50 transition-colors cursor-pointer" onClick={() => openFlow(flow.id)}>
                <div className="flex items-start justify-between mb-3">
                  <h3 className="text-sm font-semibold text-white">{flow.name}</h3>
                  <div className="flex items-center gap-2">
                    {flow.is_active && <span className="px-2 py-0.5 text-xs rounded-full bg-green-900/50 text-green-400">Active</span>}
                    <span className="text-xs text-gray-500">v{flow.version}</span>
                  </div>
                </div>
                <p className="text-xs text-gray-400 mb-3">{flow.description || 'No description'}</p>
                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span>{flow.node_count} nodes</span>
                  <span>{flow.edge_count} edges</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ── Editor view ────────────────────────────────────────────────
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <button onClick={() => { setView('list'); setTestResult(null); }} className="text-gray-400 hover:text-white transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
          </button>
          <div>
            <h1 className="text-xl font-bold text-white">{selectedFlow?.name || 'Flow Editor'}</h1>
            <p className="text-xs text-gray-400">v{selectedFlow?.version} &bull; {selectedFlow?.nodes.length} nodes &bull; {selectedFlow?.edges.length} edges</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={activateFlow} disabled={selectedFlow?.is_active} className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors ${selectedFlow?.is_active ? 'bg-green-900/30 text-green-400 cursor-default' : 'bg-green-600 hover:bg-green-700 text-white'}`}>
            {selectedFlow?.is_active ? 'Active' : 'Activate'}
          </button>
          <button onClick={() => selectedFlow && deleteFlow(selectedFlow.id)} className="px-4 py-2 text-sm bg-red-900/30 text-red-400 hover:bg-red-900/50 rounded-lg transition-colors">
            Delete
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Flow canvas (node list view) */}
        <div className="col-span-2 bg-[#1a1230] rounded-xl border border-vox-900/50 p-6">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Flow Nodes</h3>
          <div className="space-y-3">
            {selectedFlow?.nodes.map((node, i) => {
              const outgoing = selectedFlow.edges.filter(e => e.source_id === node.id);
              return (
                <div key={node.id} className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg ${NODE_COLORS[node.type] || 'bg-gray-600'} flex items-center justify-center text-white text-xs font-bold shrink-0`}>
                    {(i + 1)}
                  </div>
                  <div className="flex-1 bg-[#0f0a1e] rounded-lg p-3 border border-vox-900/30">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-white">{node.label || NODE_LABELS[node.type]}</span>
                      <span className="text-xs px-2 py-0.5 rounded bg-white/5 text-gray-400">{node.type}</span>
                    </div>
                    {node.config.text && <p className="text-xs text-gray-400 mt-1">"{node.config.text}"</p>}
                    {node.config.tool_name && <p className="text-xs text-cyan-400 mt-1">Tool: {node.config.tool_name}</p>}
                    {node.config.rules && (
                      <div className="mt-1 space-y-1">
                        {node.config.rules.map((r: any, ri: number) => (
                          <p key={ri} className="text-xs text-orange-400">if "{r.match}" → next</p>
                        ))}
                      </div>
                    )}
                    {outgoing.length > 0 && (
                      <div className="mt-2 flex gap-1">
                        {outgoing.map(e => (
                          <span key={e.id} className="text-[10px] px-1.5 py-0.5 rounded bg-vox-900/30 text-gray-500">
                            → {selectedFlow.nodes.find(n => n.id === e.target_id)?.label || 'next'}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Test panel */}
        <div className="space-y-4">
          <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Test Flow</h3>
            <p className="text-xs text-gray-400 mb-3">Enter simulated user messages (one per line) to test the flow execution.</p>
            <textarea
              value={testInputs}
              onChange={(e) => setTestInputs(e.target.value)}
              placeholder={"Hello\nI need help with my order\nOrder #12345"}
              rows={5}
              className="w-full px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500 mb-3"
            />
            <button onClick={testFlow} disabled={testing} className="w-full px-4 py-2 bg-vox-600 hover:bg-vox-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors">
              {testing ? 'Running...' : 'Run Test'}
            </button>
          </div>

          {testResult && (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Result</h3>
                <span className={`px-2 py-0.5 text-xs rounded-full ${testResult.completed ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
                  {testResult.end_reason}
                </span>
              </div>
              <div className="space-y-2 mb-3">
                {testResult.messages.map((msg, i) => (
                  <div key={i} className={`text-xs p-2 rounded ${msg.role === 'user' ? 'bg-vox-600/20 text-vox-300' : msg.role === 'system' ? 'bg-amber-900/20 text-amber-300' : msg.role === 'tool' ? 'bg-cyan-900/20 text-cyan-300' : 'bg-white/5 text-gray-300'}`}>
                    <span className="font-semibold">{msg.role}:</span> {msg.content}
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span>{testResult.path.length} nodes visited</span>
                <span>{testResult.duration_ms}ms</span>
              </div>
            </div>
          )}

          <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Node Types</h3>
            <div className="space-y-2">
              {Object.entries(NODE_LABELS).map(([type, label]) => (
                <div key={type} className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded ${NODE_COLORS[type]}`} />
                  <span className="text-xs text-gray-400">{label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
