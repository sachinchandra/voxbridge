import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { agentsApi, knowledgeBasesApi } from '../services/api';
import { AgentStats, AgentTool, KnowledgeBase } from '../types';

const LLM_OPTIONS = [
  { provider: 'openai', models: ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo'] },
  { provider: 'anthropic', models: ['claude-sonnet-4-20250514', 'claude-3-5-haiku-20241022'] },
];

const STT_OPTIONS = ['deepgram', 'google', 'azure'];
const TTS_OPTIONS = ['elevenlabs', 'openai', 'deepgram'];

const STEPS = ['Basics', 'AI Model', 'Voice', 'Behavior', 'Tools', 'Knowledge', 'Escalation', 'Review'];

const EMPTY_TOOL: AgentTool = {
  name: '',
  description: '',
  parameters: {},
  endpoint: '',
  method: 'GET',
  headers: {},
};

export default function AgentEditor() {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const isNew = agentId === 'new';

  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [stats, setStats] = useState<AgentStats | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);

  // Form state
  const [form, setForm] = useState({
    name: '',
    system_prompt: '',
    first_message: '',
    end_call_phrases: '' as string, // comma-separated, parsed on save
    stt_provider: 'deepgram',
    llm_provider: 'openai',
    llm_model: 'gpt-4o-mini',
    tts_provider: 'elevenlabs',
    tts_voice_id: '',
    max_duration_seconds: 300,
    interruption_enabled: true,
    tools: [] as AgentTool[],
    knowledge_base_id: null as string | null,
    escalation_config: {
      enabled: false,
      triggers: [] as string[],
      transfer_number: '',
    },
    status: 'draft' as string,
  });

  useEffect(() => {
    // Load knowledge bases for the dropdown
    knowledgeBasesApi.list().then(setKnowledgeBases).catch(() => {});

    if (!isNew && agentId) {
      Promise.all([
        agentsApi.get(agentId).catch(() => null),
        agentsApi.getStats(agentId).catch(() => null),
      ]).then(([agent, agentStats]) => {
        if (agent) {
          setForm({
            name: agent.name,
            system_prompt: agent.system_prompt,
            first_message: agent.first_message,
            end_call_phrases: agent.end_call_phrases.join(', '),
            stt_provider: agent.stt_provider,
            llm_provider: agent.llm_provider,
            llm_model: agent.llm_model,
            tts_provider: agent.tts_provider,
            tts_voice_id: agent.tts_voice_id,
            max_duration_seconds: agent.max_duration_seconds,
            interruption_enabled: agent.interruption_enabled,
            tools: (agent.tools || []) as AgentTool[],
            knowledge_base_id: agent.knowledge_base_id || null,
            escalation_config: agent.escalation_config as any || { enabled: false, triggers: [], transfer_number: '' },
            status: agent.status,
          });
        }
        if (agentStats) setStats(agentStats);
        setLoading(false);
      });
    }
  }, [agentId, isNew]);

  const update = (field: string, value: any) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');

    const payload = {
      name: form.name || 'Untitled Agent',
      system_prompt: form.system_prompt,
      first_message: form.first_message,
      end_call_phrases: form.end_call_phrases.split(',').map(s => s.trim()).filter(Boolean),
      stt_provider: form.stt_provider,
      llm_provider: form.llm_provider,
      llm_model: form.llm_model,
      tts_provider: form.tts_provider,
      tts_voice_id: form.tts_voice_id,
      max_duration_seconds: form.max_duration_seconds,
      interruption_enabled: form.interruption_enabled,
      tools: form.tools.filter(t => t.name.trim() && t.endpoint.trim()),
      knowledge_base_id: form.knowledge_base_id,
      escalation_config: form.escalation_config,
    };

    try {
      if (isNew) {
        const agent = await agentsApi.create(payload);
        navigate(`/dashboard/agents/${agent.id}`, { replace: true });
      } else {
        await agentsApi.update(agentId!, payload);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save agent');
    } finally {
      setSaving(false);
    }
  };

  const handleDeploy = async () => {
    setSaving(true);
    try {
      await agentsApi.update(agentId!, { status: 'active' } as any);
      update('status', 'active');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to deploy');
    } finally {
      setSaving(false);
    }
  };

  const handlePause = async () => {
    setSaving(true);
    try {
      await agentsApi.update(agentId!, { status: 'paused' } as any);
      update('status', 'paused');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to pause');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete this agent?')) return;
    try {
      await agentsApi.delete(agentId!);
      navigate('/dashboard/agents', { replace: true });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete');
    }
  };

  const currentModels = LLM_OPTIONS.find(o => o.provider === form.llm_provider)?.models || [];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-vox-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/dashboard/agents')}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 className="text-2xl font-bold text-white">
              {isNew ? 'Create Agent' : form.name || 'Edit Agent'}
            </h1>
            {!isNew && (
              <span className={`inline-block mt-1 px-2 py-0.5 text-xs rounded-full ${
                form.status === 'active' ? 'bg-emerald-600/20 text-emerald-300' :
                form.status === 'paused' ? 'bg-amber-600/20 text-amber-300' :
                'bg-gray-600/20 text-gray-300'
              }`}>
                {form.status.charAt(0).toUpperCase() + form.status.slice(1)}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!isNew && form.status !== 'active' && (
            <button onClick={handleDeploy} disabled={saving}
              className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition-colors disabled:opacity-50">
              Deploy
            </button>
          )}
          {!isNew && form.status === 'active' && (
            <button onClick={handlePause} disabled={saving}
              className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium transition-colors disabled:opacity-50">
              Pause
            </button>
          )}
          <button onClick={handleSave} disabled={saving}
            className="px-4 py-2 rounded-lg bg-vox-600 hover:bg-vox-500 text-white text-sm font-medium transition-colors disabled:opacity-50">
            {saving ? 'Saving...' : 'Save'}
          </button>
          {!isNew && (
            <button onClick={handleDelete}
              className="px-4 py-2 rounded-lg bg-red-600/20 hover:bg-red-600/40 text-red-300 text-sm font-medium transition-colors">
              Delete
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 mb-6 text-red-300 text-sm">{error}</div>
      )}

      {/* Step navigation */}
      <div className="flex items-center gap-1 mb-8 overflow-x-auto">
        {STEPS.map((label, i) => (
          <button
            key={label}
            onClick={() => setStep(i)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
              step === i
                ? 'bg-vox-600/20 text-vox-300'
                : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}
          >
            {label}
          </button>
        ))}
        {!isNew && (
          <button
            onClick={() => setStep(STEPS.length)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
              step === STEPS.length ? 'bg-vox-600/20 text-vox-300' : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}
          >
            Stats
          </button>
        )}
      </div>

      {/* Step content */}
      <div className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50">

        {/* Step 0: Basics */}
        {step === 0 && (
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Agent Name</label>
              <input
                type="text" value={form.name} onChange={(e) => update('name', e.target.value)}
                placeholder="e.g. Customer Support Bot"
                className="w-full px-4 py-2.5 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white focus:border-vox-500 focus:outline-none transition-colors"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">System Prompt</label>
              <p className="text-xs text-gray-500 mb-2">Tell the AI who it is, what it knows, and how to behave.</p>
              <textarea
                value={form.system_prompt} onChange={(e) => update('system_prompt', e.target.value)}
                rows={8}
                placeholder="You are a friendly customer support agent for Acme Corp. You help customers with order status, returns, and product questions. Be concise and helpful. If you can't help, offer to transfer to a human agent."
                className="w-full px-4 py-2.5 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white focus:border-vox-500 focus:outline-none transition-colors font-mono text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">First Message</label>
              <p className="text-xs text-gray-500 mb-2">What the AI says when it picks up a call.</p>
              <input
                type="text" value={form.first_message} onChange={(e) => update('first_message', e.target.value)}
                placeholder="Hello! Thank you for calling Acme Corp. How can I help you today?"
                className="w-full px-4 py-2.5 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white focus:border-vox-500 focus:outline-none transition-colors"
              />
            </div>
          </div>
        )}

        {/* Step 1: AI Model */}
        {step === 1 && (
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">LLM Provider</label>
              <div className="grid grid-cols-2 gap-3">
                {LLM_OPTIONS.map((opt) => (
                  <button
                    key={opt.provider}
                    onClick={() => {
                      update('llm_provider', opt.provider);
                      update('llm_model', opt.models[0]);
                    }}
                    className={`p-4 rounded-lg border text-left transition-colors ${
                      form.llm_provider === opt.provider
                        ? 'border-vox-500 bg-vox-600/10'
                        : 'border-vox-900/50 hover:border-vox-600/30 bg-[#0f0a1e]'
                    }`}
                  >
                    <div className="text-white font-medium">{opt.provider === 'openai' ? 'OpenAI' : 'Anthropic Claude'}</div>
                    <div className="text-xs text-gray-400 mt-1">{opt.models.join(', ')}</div>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Model</label>
              <select
                value={form.llm_model}
                onChange={(e) => update('llm_model', e.target.value)}
                className="w-full px-4 py-2.5 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white focus:border-vox-500 focus:outline-none"
              >
                {currentModels.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          </div>
        )}

        {/* Step 2: Voice */}
        {step === 2 && (
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Speech-to-Text Provider</label>
              <div className="grid grid-cols-3 gap-3">
                {STT_OPTIONS.map((stt) => (
                  <button
                    key={stt}
                    onClick={() => update('stt_provider', stt)}
                    className={`p-4 rounded-lg border text-center transition-colors ${
                      form.stt_provider === stt
                        ? 'border-vox-500 bg-vox-600/10'
                        : 'border-vox-900/50 hover:border-vox-600/30 bg-[#0f0a1e]'
                    }`}
                  >
                    <div className="text-white font-medium capitalize">{stt}</div>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Text-to-Speech Provider</label>
              <div className="grid grid-cols-3 gap-3">
                {TTS_OPTIONS.map((tts) => (
                  <button
                    key={tts}
                    onClick={() => update('tts_provider', tts)}
                    className={`p-4 rounded-lg border text-center transition-colors ${
                      form.tts_provider === tts
                        ? 'border-vox-500 bg-vox-600/10'
                        : 'border-vox-900/50 hover:border-vox-600/30 bg-[#0f0a1e]'
                    }`}
                  >
                    <div className="text-white font-medium capitalize">{tts === 'elevenlabs' ? 'ElevenLabs' : tts}</div>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Voice ID</label>
              <p className="text-xs text-gray-500 mb-2">ElevenLabs voice ID or leave blank for default</p>
              <input
                type="text" value={form.tts_voice_id} onChange={(e) => update('tts_voice_id', e.target.value)}
                placeholder="e.g. 21m00Tcm4TlvDq8ikWAM"
                className="w-full px-4 py-2.5 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white focus:border-vox-500 focus:outline-none transition-colors"
              />
            </div>
          </div>
        )}

        {/* Step 3: Behavior */}
        {step === 3 && (
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Max Call Duration (seconds)</label>
              <input
                type="number" value={form.max_duration_seconds}
                onChange={(e) => update('max_duration_seconds', parseInt(e.target.value) || 300)}
                min={30} max={3600}
                className="w-full px-4 py-2.5 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white focus:border-vox-500 focus:outline-none transition-colors"
              />
              <p className="text-xs text-gray-500 mt-1">{Math.floor(form.max_duration_seconds / 60)}m {form.max_duration_seconds % 60}s</p>
            </div>
            <div>
              <label className="flex items-center gap-3 cursor-pointer">
                <div
                  onClick={() => update('interruption_enabled', !form.interruption_enabled)}
                  className={`w-11 h-6 rounded-full transition-colors relative ${form.interruption_enabled ? 'bg-vox-600' : 'bg-gray-600'}`}
                >
                  <div className={`w-5 h-5 rounded-full bg-white absolute top-0.5 transition-transform ${form.interruption_enabled ? 'translate-x-5.5 left-[22px]' : 'left-0.5'}`}></div>
                </div>
                <div>
                  <span className="text-sm font-medium text-gray-300">Allow Interruptions (Barge-in)</span>
                  <p className="text-xs text-gray-500">User can interrupt the AI while it's speaking</p>
                </div>
              </label>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">End Call Phrases</label>
              <p className="text-xs text-gray-500 mb-2">Comma-separated phrases that trigger call end</p>
              <input
                type="text" value={form.end_call_phrases}
                onChange={(e) => update('end_call_phrases', e.target.value)}
                placeholder="goodbye, bye, have a nice day, that's all"
                className="w-full px-4 py-2.5 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white focus:border-vox-500 focus:outline-none transition-colors"
              />
            </div>
          </div>
        )}

        {/* Step 4: Tools */}
        {step === 4 && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-medium text-white">Function Calling Tools</h3>
                <p className="text-xs text-gray-500 mt-1">Define HTTP APIs your agent can call during conversations</p>
              </div>
              <button
                onClick={() => update('tools', [...form.tools, { ...EMPTY_TOOL }])}
                className="px-3 py-1.5 rounded-lg bg-vox-600 hover:bg-vox-500 text-white text-xs font-medium transition-colors flex items-center gap-1"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Add Tool
              </button>
            </div>

            {form.tools.length === 0 ? (
              <div className="text-center py-10 bg-[#0f0a1e] rounded-lg border border-vox-900/30">
                <svg className="w-10 h-10 text-gray-600 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11.42 15.17l-5.384-5.383a1.5 1.5 0 010-2.121l.354-.354a1.5 1.5 0 012.121 0l3.263 3.263 3.263-3.263a1.5 1.5 0 012.121 0l.354.354a1.5 1.5 0 010 2.121L12.58 15.17a.82.82 0 01-1.16 0z" />
                </svg>
                <p className="text-gray-400 text-sm">No tools configured</p>
                <p className="text-gray-600 text-xs mt-1">Add tools to let your agent look up orders, check inventory, etc.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {form.tools.map((tool, idx) => (
                  <div key={idx} className="bg-[#0f0a1e] rounded-lg border border-vox-900/30 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-gray-500 uppercase">Tool {idx + 1}</span>
                      <button
                        onClick={() => update('tools', form.tools.filter((_, i) => i !== idx))}
                        className="text-gray-600 hover:text-red-400 transition-colors"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-400 mb-1">Name</label>
                        <input
                          type="text" value={tool.name}
                          onChange={(e) => {
                            const updated = [...form.tools];
                            updated[idx] = { ...updated[idx], name: e.target.value };
                            update('tools', updated);
                          }}
                          placeholder="lookup_order"
                          className="w-full px-3 py-2 rounded-lg bg-[#1a1230] border border-vox-900/50 text-white text-sm focus:border-vox-500 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-400 mb-1">Method</label>
                        <select
                          value={tool.method}
                          onChange={(e) => {
                            const updated = [...form.tools];
                            updated[idx] = { ...updated[idx], method: e.target.value };
                            update('tools', updated);
                          }}
                          className="w-full px-3 py-2 rounded-lg bg-[#1a1230] border border-vox-900/50 text-white text-sm focus:border-vox-500 focus:outline-none"
                        >
                          <option value="GET">GET</option>
                          <option value="POST">POST</option>
                          <option value="PUT">PUT</option>
                          <option value="PATCH">PATCH</option>
                          <option value="DELETE">DELETE</option>
                        </select>
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-400 mb-1">Description</label>
                      <input
                        type="text" value={tool.description}
                        onChange={(e) => {
                          const updated = [...form.tools];
                          updated[idx] = { ...updated[idx], description: e.target.value };
                          update('tools', updated);
                        }}
                        placeholder="Look up order status by order ID"
                        className="w-full px-3 py-2 rounded-lg bg-[#1a1230] border border-vox-900/50 text-white text-sm focus:border-vox-500 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-400 mb-1">Endpoint URL</label>
                      <input
                        type="text" value={tool.endpoint}
                        onChange={(e) => {
                          const updated = [...form.tools];
                          updated[idx] = { ...updated[idx], endpoint: e.target.value };
                          update('tools', updated);
                        }}
                        placeholder="https://api.example.com/orders/{{order_id}}"
                        className="w-full px-3 py-2 rounded-lg bg-[#1a1230] border border-vox-900/50 text-white text-sm focus:border-vox-500 focus:outline-none font-mono"
                      />
                      <p className="text-xs text-gray-600 mt-1">Use {'{{param}}'} for template variables from function arguments</p>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-400 mb-1">Parameters (JSON Schema)</label>
                      <textarea
                        value={typeof tool.parameters === 'string' ? tool.parameters : JSON.stringify(tool.parameters, null, 2)}
                        onChange={(e) => {
                          const updated = [...form.tools];
                          try {
                            updated[idx] = { ...updated[idx], parameters: JSON.parse(e.target.value) };
                          } catch {
                            updated[idx] = { ...updated[idx], parameters: e.target.value as any };
                          }
                          update('tools', updated);
                        }}
                        rows={3}
                        placeholder={'{\n  "type": "object",\n  "properties": {\n    "order_id": { "type": "string", "description": "The order ID" }\n  },\n  "required": ["order_id"]\n}'}
                        className="w-full px-3 py-2 rounded-lg bg-[#1a1230] border border-vox-900/50 text-white text-xs focus:border-vox-500 focus:outline-none font-mono resize-none"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-400 mb-1">Headers (optional, JSON)</label>
                      <input
                        type="text"
                        value={typeof tool.headers === 'string' ? tool.headers : JSON.stringify(tool.headers || {})}
                        onChange={(e) => {
                          const updated = [...form.tools];
                          try {
                            updated[idx] = { ...updated[idx], headers: JSON.parse(e.target.value) };
                          } catch {
                            updated[idx] = { ...updated[idx], headers: e.target.value as any };
                          }
                          update('tools', updated);
                        }}
                        placeholder='{"Authorization": "Bearer {{api_key}}"}'
                        className="w-full px-3 py-2 rounded-lg bg-[#1a1230] border border-vox-900/50 text-white text-xs focus:border-vox-500 focus:outline-none font-mono"
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Step 5: Knowledge Base */}
        {step === 5 && (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-medium text-white">Knowledge Base</h3>
              <p className="text-xs text-gray-500 mt-1">Attach a knowledge base so the agent can answer questions from your documents using RAG</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Select Knowledge Base</label>
              <select
                value={form.knowledge_base_id || ''}
                onChange={(e) => update('knowledge_base_id', e.target.value || null)}
                className="w-full px-4 py-2.5 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white focus:border-vox-500 focus:outline-none"
              >
                <option value="">None — Agent uses only its system prompt</option>
                {knowledgeBases.map((kb) => (
                  <option key={kb.id} value={kb.id}>
                    {kb.name} ({kb.document_count} docs, {kb.total_chunks} chunks)
                  </option>
                ))}
              </select>
            </div>

            {form.knowledge_base_id && (() => {
              const kb = knowledgeBases.find(k => k.id === form.knowledge_base_id);
              return kb ? (
                <div className="bg-[#0f0a1e] rounded-lg border border-vox-500/20 p-5">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-lg bg-vox-600/20 flex items-center justify-center">
                      <svg className="w-5 h-5 text-vox-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                      </svg>
                    </div>
                    <div>
                      <h4 className="text-white font-medium">{kb.name}</h4>
                      {kb.description && <p className="text-gray-500 text-xs">{kb.description}</p>}
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-[#1a1230] rounded-lg p-3 text-center">
                      <p className="text-lg font-bold text-white">{kb.document_count}</p>
                      <p className="text-xs text-gray-500">Documents</p>
                    </div>
                    <div className="bg-[#1a1230] rounded-lg p-3 text-center">
                      <p className="text-lg font-bold text-white">{kb.total_chunks}</p>
                      <p className="text-xs text-gray-500">Chunks</p>
                    </div>
                    <div className="bg-[#1a1230] rounded-lg p-3 text-center">
                      <p className="text-lg font-bold text-white">{kb.embedding_model.replace('text-embedding-', '')}</p>
                      <p className="text-xs text-gray-500">Model</p>
                    </div>
                  </div>
                  <div className="mt-3 p-3 bg-vox-600/5 rounded-lg border border-vox-900/20">
                    <p className="text-xs text-gray-400">
                      <strong className="text-gray-300">How RAG works:</strong> When a caller asks a question, the agent will search this knowledge base for relevant document chunks and include them as context in its response.
                    </p>
                  </div>
                </div>
              ) : null;
            })()}

            {knowledgeBases.length === 0 && (
              <div className="text-center py-8 bg-[#0f0a1e] rounded-lg border border-vox-900/30">
                <svg className="w-10 h-10 text-gray-600 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
                <p className="text-gray-400 text-sm">No knowledge bases available</p>
                <p className="text-gray-600 text-xs mt-1">Create one in the Knowledge Base section, then come back here to attach it</p>
              </div>
            )}
          </div>
        )}

        {/* Step 6: Escalation */}
        {step === 6 && (
          <div className="space-y-6">
            <div>
              <label className="flex items-center gap-3 cursor-pointer mb-4">
                <div
                  onClick={() => update('escalation_config', { ...form.escalation_config, enabled: !form.escalation_config.enabled })}
                  className={`w-11 h-6 rounded-full transition-colors relative ${form.escalation_config.enabled ? 'bg-vox-600' : 'bg-gray-600'}`}
                >
                  <div className={`w-5 h-5 rounded-full bg-white absolute top-0.5 transition-transform ${form.escalation_config.enabled ? 'left-[22px]' : 'left-0.5'}`}></div>
                </div>
                <div>
                  <span className="text-sm font-medium text-gray-300">Enable Human Escalation</span>
                  <p className="text-xs text-gray-500">Transfer to a human when the AI can't help</p>
                </div>
              </label>
            </div>

            {form.escalation_config.enabled && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Escalation Triggers</label>
                  <p className="text-xs text-gray-500 mb-2">When should the AI transfer to a human?</p>
                  <div className="space-y-2">
                    {['Caller requests human agent', 'Caller is angry or frustrated', 'AI cannot answer the question', 'Sensitive topics (billing disputes, legal)'].map((trigger) => (
                      <label key={trigger} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={form.escalation_config.triggers?.includes(trigger) || false}
                          onChange={(e) => {
                            const triggers = form.escalation_config.triggers || [];
                            if (e.target.checked) {
                              update('escalation_config', { ...form.escalation_config, triggers: [...triggers, trigger] });
                            } else {
                              update('escalation_config', { ...form.escalation_config, triggers: triggers.filter((t: string) => t !== trigger) });
                            }
                          }}
                          className="rounded border-vox-900 bg-[#0f0a1e] text-vox-500 focus:ring-vox-500"
                        />
                        {trigger}
                      </label>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Transfer Phone Number</label>
                  <input
                    type="text"
                    value={form.escalation_config.transfer_number || ''}
                    onChange={(e) => update('escalation_config', { ...form.escalation_config, transfer_number: e.target.value })}
                    placeholder="+14155551234"
                    className="w-full px-4 py-2.5 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white focus:border-vox-500 focus:outline-none transition-colors"
                  />
                </div>
              </>
            )}
          </div>
        )}

        {/* Step 7: Review */}
        {step === 7 && (
          <div className="space-y-4">
            <h3 className="text-lg font-medium text-white mb-4">Review Configuration</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <ReviewItem label="Name" value={form.name || 'Untitled'} />
              <ReviewItem label="Status" value={form.status} />
              <ReviewItem label="LLM" value={`${form.llm_provider} / ${form.llm_model}`} />
              <ReviewItem label="STT" value={form.stt_provider} />
              <ReviewItem label="TTS" value={form.tts_provider} />
              <ReviewItem label="Voice ID" value={form.tts_voice_id || 'Default'} />
              <ReviewItem label="Max Duration" value={`${Math.floor(form.max_duration_seconds / 60)}m ${form.max_duration_seconds % 60}s`} />
              <ReviewItem label="Interruptions" value={form.interruption_enabled ? 'Enabled' : 'Disabled'} />
              <ReviewItem label="Tools" value={form.tools.filter(t => t.name.trim()).length > 0 ? `${form.tools.filter(t => t.name.trim()).length} configured` : 'None'} />
              <ReviewItem label="Knowledge Base" value={form.knowledge_base_id ? (knowledgeBases.find(k => k.id === form.knowledge_base_id)?.name || 'Selected') : 'None'} />
              <ReviewItem label="Escalation" value={form.escalation_config.enabled ? 'Enabled' : 'Disabled'} />
            </div>
            {form.system_prompt && (
              <div className="mt-4">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">System Prompt</p>
                <div className="bg-[#0f0a1e] rounded-lg p-3 text-sm text-gray-300 font-mono whitespace-pre-wrap max-h-40 overflow-y-auto">
                  {form.system_prompt}
                </div>
              </div>
            )}
            {form.first_message && (
              <div className="mt-2">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">First Message</p>
                <div className="bg-[#0f0a1e] rounded-lg p-3 text-sm text-gray-300">
                  "{form.first_message}"
                </div>
              </div>
            )}
          </div>
        )}

        {/* Stats (edit mode only) */}
        {step === STEPS.length && stats && (
          <div className="space-y-6">
            <h3 className="text-lg font-medium text-white">Performance</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard label="Total Calls" value={String(stats.total_calls)} />
              <StatCard label="Containment" value={`${stats.containment_rate}%`} sub="AI-handled" />
              <StatCard label="Avg Duration" value={`${stats.avg_duration_seconds.toFixed(0)}s`} />
              <StatCard label="Resolution" value={`${stats.resolution_rate}%`} />
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard label="Completed" value={String(stats.completed_calls)} />
              <StatCard label="Escalated" value={String(stats.escalated_calls)} />
              <StatCard label="Failed" value={String(stats.failed_calls)} />
              <StatCard label="Cost" value={`$${(stats.total_cost_cents / 100).toFixed(2)}`} />
            </div>
            {stats.calls_by_day.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-300 mb-3">Calls per Day</h4>
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={stats.calls_by_day}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#2a2040" />
                      <XAxis dataKey="date" stroke="#6b7280" fontSize={11} tickFormatter={(v) => v.slice(5)} />
                      <YAxis stroke="#6b7280" fontSize={11} />
                      <Tooltip
                        contentStyle={{ background: '#1a1230', border: '1px solid #3b0f7a', borderRadius: '8px', color: '#f3f0ff' }}
                      />
                      <Bar dataKey="calls" fill="#7c3aed" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>
        )}
        {step === STEPS.length && !stats && (
          <div className="text-center py-8 text-gray-400">No stats available yet. Deploy your agent and make some calls!</div>
        )}
      </div>

      {/* Step navigation buttons */}
      <div className="flex items-center justify-between mt-6">
        <button
          onClick={() => setStep(Math.max(0, step - 1))}
          disabled={step === 0}
          className="px-4 py-2 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition-colors disabled:opacity-30"
        >
          Previous
        </button>
        <div className="flex items-center gap-1">
          {STEPS.map((_, i) => (
            <div key={i} className={`w-2 h-2 rounded-full transition-colors ${step === i ? 'bg-vox-500' : 'bg-gray-600'}`} />
          ))}
        </div>
        {step < STEPS.length - 1 ? (
          <button
            onClick={() => setStep(step + 1)}
            className="px-4 py-2 rounded-lg bg-vox-600 hover:bg-vox-500 text-white text-sm font-medium transition-colors"
          >
            Next
          </button>
        ) : (
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2 rounded-lg bg-vox-600 hover:bg-vox-500 text-white text-sm font-medium transition-colors disabled:opacity-50"
          >
            {saving ? 'Saving...' : isNew ? 'Create Agent' : 'Save Changes'}
          </button>
        )}
      </div>
    </div>
  );
}

function ReviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[#0f0a1e] rounded-lg p-3">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-sm text-white mt-0.5 capitalize">{value}</p>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-[#0f0a1e] rounded-lg p-4">
      <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</p>
      <p className="text-xl font-bold text-white mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
    </div>
  );
}
