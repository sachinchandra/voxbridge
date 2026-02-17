import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { agentsApi } from '../services/api';
import { AgentStats } from '../types';

const LLM_OPTIONS = [
  { provider: 'openai', models: ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo'] },
  { provider: 'anthropic', models: ['claude-sonnet-4-20250514', 'claude-3-5-haiku-20241022'] },
];

const STT_OPTIONS = ['deepgram', 'google', 'azure'];
const TTS_OPTIONS = ['elevenlabs', 'openai', 'deepgram'];

const STEPS = ['Basics', 'AI Model', 'Voice', 'Behavior', 'Escalation', 'Review'];

export default function AgentEditor() {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const isNew = agentId === 'new';

  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [stats, setStats] = useState<AgentStats | null>(null);

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
    escalation_config: {
      enabled: false,
      triggers: [] as string[],
      transfer_number: '',
    },
    status: 'draft' as string,
  });

  useEffect(() => {
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
            onClick={() => setStep(6)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
              step === 6 ? 'bg-vox-600/20 text-vox-300' : 'text-gray-400 hover:text-white hover:bg-white/5'
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

        {/* Step 4: Escalation */}
        {step === 4 && (
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

        {/* Step 5: Review */}
        {step === 5 && (
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

        {/* Step 6: Stats (edit mode only) */}
        {step === 6 && stats && (
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
        {step === 6 && !stats && (
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
