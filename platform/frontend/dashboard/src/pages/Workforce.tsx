import React, { useState, useEffect } from 'react';
import { workforceApi } from '../services/api';
import {
  HumanAgentItem, EscalationItem, StaffingForecastItem, ROIEstimateItem,
  WorkforceDashboardData, QueueStatusData,
} from '../types';

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  available: { bg: 'bg-green-900/30', text: 'text-green-400' },
  busy: { bg: 'bg-red-900/30', text: 'text-red-400' },
  offline: { bg: 'bg-gray-800', text: 'text-gray-400' },
  break: { bg: 'bg-amber-900/30', text: 'text-amber-400' },
};

const PRIORITY_COLORS: Record<string, string> = {
  low: 'text-gray-400',
  normal: 'text-blue-400',
  high: 'text-amber-400',
  urgent: 'text-red-400',
};

type Tab = 'dashboard' | 'agents' | 'escalations' | 'forecast';

export default function Workforce() {
  const [tab, setTab] = useState<Tab>('dashboard');
  const [loading, setLoading] = useState(true);

  // Dashboard
  const [dashboard, setDashboard] = useState<WorkforceDashboardData | null>(null);

  // Agents
  const [agents, setAgents] = useState<HumanAgentItem[]>([]);
  const [showAddAgent, setShowAddAgent] = useState(false);
  const [newAgent, setNewAgent] = useState({ name: '', email: '', skills: '', department_id: '', shift_start: '09:00', shift_end: '17:00' });

  // Escalations
  const [escalations, setEscalations] = useState<EscalationItem[]>([]);
  const [queueStatus, setQueueStatus] = useState<QueueStatusData | null>(null);

  // Forecast & ROI
  const [forecasts, setForecasts] = useState<StaffingForecastItem[]>([]);
  const [forecastDate, setForecastDate] = useState(new Date().toISOString().split('T')[0]);
  const [roi, setRoi] = useState<ROIEstimateItem | null>(null);
  const [roiParams, setRoiParams] = useState({
    total_monthly_calls: 10000,
    containment_rate: 80,
    human_agent_hourly_rate_cents: 2000,
    avg_call_duration_minutes: 5,
  });

  const fetchDashboard = async () => {
    try {
      const d = await workforceApi.getDashboard();
      setDashboard(d);
    } catch {}
  };

  const fetchAgents = async () => {
    try {
      const a = await workforceApi.listAgents();
      setAgents(a);
    } catch {}
  };

  const fetchEscalations = async () => {
    try {
      const [e, q] = await Promise.all([workforceApi.listEscalations(), workforceApi.getQueueStatus()]);
      setEscalations(e);
      setQueueStatus(q);
    } catch {}
  };

  useEffect(() => {
    const init = async () => {
      await Promise.all([fetchDashboard(), fetchAgents(), fetchEscalations()]);
      setLoading(false);
    };
    init();
  }, []);

  // Agent actions
  const addAgent = async () => {
    if (!newAgent.name.trim()) return;
    try {
      await workforceApi.createAgent({
        name: newAgent.name,
        email: newAgent.email,
        skills: newAgent.skills ? newAgent.skills.split(',').map(s => s.trim()) : [],
        department_id: newAgent.department_id,
        shift_start: newAgent.shift_start,
        shift_end: newAgent.shift_end,
      });
      setShowAddAgent(false);
      setNewAgent({ name: '', email: '', skills: '', department_id: '', shift_start: '09:00', shift_end: '17:00' });
      fetchAgents();
      fetchDashboard();
    } catch {}
  };

  const toggleStatus = async (agent: HumanAgentItem, status: string) => {
    try {
      await workforceApi.setAgentStatus(agent.id, status);
      fetchAgents();
      fetchDashboard();
    } catch {}
  };

  const deleteAgent = async (agentId: string) => {
    try {
      await workforceApi.deleteAgent(agentId);
      fetchAgents();
      fetchDashboard();
    } catch {}
  };

  // Escalation actions
  const autoAssign = async (escId: string) => {
    try {
      await workforceApi.autoAssignEscalation(escId);
      fetchEscalations();
      fetchAgents();
      fetchDashboard();
    } catch {}
  };

  const resolveEsc = async (escId: string) => {
    try {
      await workforceApi.resolveEscalation(escId);
      fetchEscalations();
      fetchAgents();
      fetchDashboard();
    } catch {}
  };

  // Forecast
  const generateForecast = async () => {
    try {
      const f = await workforceApi.generateForecast({ date: forecastDate });
      setForecasts(f);
    } catch {}
  };

  // ROI
  const calculateROI = async () => {
    try {
      const r = await workforceApi.calculateROI({
        total_monthly_calls: roiParams.total_monthly_calls,
        containment_rate: roiParams.containment_rate / 100,
        human_agent_hourly_rate_cents: roiParams.human_agent_hourly_rate_cents,
        avg_call_duration_minutes: roiParams.avg_call_duration_minutes,
      });
      setRoi(r);
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
          <h1 className="text-2xl font-bold text-white">Workforce Management</h1>
          <p className="text-sm text-gray-400 mt-1">Hybrid AI + Human workforce — escalations, forecasting, and ROI</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6">
        {([
          { key: 'dashboard', label: 'Dashboard' },
          { key: 'agents', label: `Human Agents (${agents.length})` },
          { key: 'escalations', label: `Escalation Queue (${queueStatus?.waiting || 0})` },
          { key: 'forecast', label: 'Forecasting & ROI' },
        ] as const).map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key as Tab)}
            className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors ${
              tab === t.key ? 'bg-vox-600/20 text-vox-300' : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Dashboard Tab ─────────────────────────────── */}
      {tab === 'dashboard' && dashboard && (
        <div>
          <div className="grid grid-cols-5 gap-4 mb-6">
            {[
              { label: 'AI Containment', value: `${(dashboard.containment_rate * 100).toFixed(1)}%`, color: dashboard.containment_rate > 0.7 ? 'text-green-400' : 'text-amber-400' },
              { label: 'Queue Length', value: dashboard.queue_length, color: dashboard.queue_length > 5 ? 'text-red-400' : 'text-white' },
              { label: 'Avg Wait Time', value: `${dashboard.avg_wait_time_seconds.toFixed(0)}s`, color: dashboard.avg_wait_time_seconds > 120 ? 'text-red-400' : 'text-white' },
              { label: 'Active Agents', value: `${dashboard.active_human_agents}/${dashboard.total_human_agents}`, color: 'text-vox-400' },
              { label: 'Escalation Rate', value: `${(dashboard.escalation_rate * 100).toFixed(1)}%`, color: dashboard.escalation_rate > 0.3 ? 'text-amber-400' : 'text-green-400' },
            ].map(kpi => (
              <div key={kpi.label} className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-4 text-center">
                <p className="text-xs text-gray-500 uppercase tracking-wider">{kpi.label}</p>
                <p className={`text-2xl font-bold mt-1 ${kpi.color}`}>{kpi.value}</p>
              </div>
            ))}
          </div>

          {/* Agent status breakdown */}
          <div className="grid grid-cols-2 gap-6 mb-6">
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
              <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Agents by Status</h3>
              <div className="space-y-3">
                {Object.entries(dashboard.agents_by_status).map(([status, count]) => {
                  const style = STATUS_COLORS[status] || STATUS_COLORS.offline;
                  return (
                    <div key={status} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className={`inline-block w-3 h-3 rounded-full ${style.bg}`} />
                        <span className={`text-sm capitalize ${style.text}`}>{status}</span>
                      </div>
                      <span className="text-sm font-bold text-white">{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
              <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Containment Trend</h3>
              {dashboard.containment_trend.length > 0 ? (
                <div className="space-y-2">
                  {dashboard.containment_trend.slice(-6).map((entry, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <span className="text-xs text-gray-500 w-20">{entry.period}</span>
                      <div className="flex-1 bg-[#0f0a1e] rounded-full h-4 overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-vox-600 to-vox-400 rounded-full"
                          style={{ width: `${entry.containment_rate * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-white w-12 text-right">{(entry.containment_rate * 100).toFixed(1)}%</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-gray-500">No trend data yet</p>
              )}
            </div>
          </div>

          {/* Recent escalations */}
          {dashboard.recent_escalations.length > 0 && (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
              <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Recent Escalations</h3>
              <div className="space-y-2">
                {dashboard.recent_escalations.map(esc => (
                  <div key={esc.id} className="flex items-center justify-between bg-[#0f0a1e] rounded-lg p-3">
                    <div className="flex items-center gap-3">
                      <span className={`text-xs font-medium uppercase ${PRIORITY_COLORS[esc.priority]}`}>{esc.priority}</span>
                      <span className="text-sm text-white">{esc.reason || esc.call_id}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-0.5 text-xs rounded-full ${STATUS_COLORS[esc.status]?.bg || ''} ${STATUS_COLORS[esc.status]?.text || 'text-gray-400'}`}>
                        {esc.status}
                      </span>
                      <span className="text-xs text-gray-500">{new Date(esc.created_at).toLocaleTimeString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Agents Tab ────────────────────────────────── */}
      {tab === 'agents' && (
        <div>
          <div className="flex justify-end mb-4">
            <button onClick={() => setShowAddAgent(true)} className="px-4 py-2 bg-vox-600 hover:bg-vox-700 text-white rounded-lg text-sm font-medium transition-colors">
              + Add Agent
            </button>
          </div>

          {showAddAgent && (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5 mb-4">
              <h3 className="text-sm font-semibold text-white mb-4">Add Human Agent</h3>
              <div className="grid grid-cols-3 gap-3 mb-4">
                <input value={newAgent.name} onChange={e => setNewAgent({ ...newAgent, name: e.target.value })} placeholder="Name *" className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500" />
                <input value={newAgent.email} onChange={e => setNewAgent({ ...newAgent, email: e.target.value })} placeholder="Email" className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500" />
                <input value={newAgent.skills} onChange={e => setNewAgent({ ...newAgent, skills: e.target.value })} placeholder="Skills (comma separated)" className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500" />
                <input value={newAgent.department_id} onChange={e => setNewAgent({ ...newAgent, department_id: e.target.value })} placeholder="Department ID" className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500" />
                <input value={newAgent.shift_start} onChange={e => setNewAgent({ ...newAgent, shift_start: e.target.value })} placeholder="Shift Start (HH:MM)" className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500" />
                <input value={newAgent.shift_end} onChange={e => setNewAgent({ ...newAgent, shift_end: e.target.value })} placeholder="Shift End (HH:MM)" className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500" />
              </div>
              <div className="flex gap-2">
                <button onClick={addAgent} className="px-4 py-2 bg-vox-600 hover:bg-vox-700 text-white rounded-lg text-sm font-medium transition-colors">Create</button>
                <button onClick={() => setShowAddAgent(false)} className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm font-medium transition-colors">Cancel</button>
              </div>
            </div>
          )}

          {agents.length === 0 ? (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-12 text-center">
              <h2 className="text-lg font-semibold text-white mb-2">No human agents yet</h2>
              <p className="text-sm text-gray-400 mb-4">Add human agents to handle escalated calls.</p>
              <button onClick={() => setShowAddAgent(true)} className="px-6 py-3 bg-vox-600 hover:bg-vox-700 text-white rounded-lg font-medium transition-colors">
                Add First Agent
              </button>
            </div>
          ) : (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-vox-900/50">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Name</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Status</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Department</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Shift</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Calls Today</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {agents.map(agent => {
                    const style = STATUS_COLORS[agent.status] || STATUS_COLORS.offline;
                    return (
                      <tr key={agent.id} className="border-b border-vox-900/30 hover:bg-white/5">
                        <td className="px-4 py-3">
                          <div>
                            <span className="text-white font-medium">{agent.name}</span>
                            {agent.email && <span className="text-xs text-gray-500 block">{agent.email}</span>}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 text-xs rounded-full capitalize ${style.bg} ${style.text}`}>
                            {agent.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-400">{agent.department_id || '-'}</td>
                        <td className="px-4 py-3 text-gray-400">{agent.shift_start && agent.shift_end ? `${agent.shift_start}-${agent.shift_end}` : '-'}</td>
                        <td className="px-4 py-3 text-white">{agent.calls_handled_today}</td>
                        <td className="px-4 py-3">
                          <div className="flex gap-1">
                            {agent.status !== 'available' && (
                              <button onClick={() => toggleStatus(agent, 'available')} className="px-2 py-1 text-xs bg-green-900/30 text-green-400 hover:bg-green-900/50 rounded transition-colors">Available</button>
                            )}
                            {agent.status !== 'break' && (
                              <button onClick={() => toggleStatus(agent, 'break')} className="px-2 py-1 text-xs bg-amber-900/30 text-amber-400 hover:bg-amber-900/50 rounded transition-colors">Break</button>
                            )}
                            {agent.status !== 'offline' && (
                              <button onClick={() => toggleStatus(agent, 'offline')} className="px-2 py-1 text-xs bg-gray-800 text-gray-400 hover:bg-gray-700 rounded transition-colors">Offline</button>
                            )}
                            <button onClick={() => deleteAgent(agent.id)} className="px-2 py-1 text-xs bg-red-900/30 text-red-400 hover:bg-red-900/50 rounded transition-colors">Delete</button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Escalation Queue Tab ──────────────────────── */}
      {tab === 'escalations' && (
        <div>
          {queueStatus && (
            <div className="grid grid-cols-5 gap-4 mb-6">
              {[
                { label: 'Waiting', value: queueStatus.waiting, color: queueStatus.waiting > 0 ? 'text-amber-400' : 'text-white' },
                { label: 'Assigned', value: queueStatus.assigned, color: 'text-blue-400' },
                { label: 'Resolved Today', value: queueStatus.resolved_today, color: 'text-green-400' },
                { label: 'Abandoned', value: queueStatus.abandoned_today, color: queueStatus.abandoned_today > 0 ? 'text-red-400' : 'text-gray-400' },
                { label: 'Avg Wait', value: `${queueStatus.avg_wait_time_seconds.toFixed(0)}s`, color: 'text-white' },
              ].map(kpi => (
                <div key={kpi.label} className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-4 text-center">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">{kpi.label}</p>
                  <p className={`text-2xl font-bold mt-1 ${kpi.color}`}>{kpi.value}</p>
                </div>
              ))}
            </div>
          )}

          {escalations.length === 0 ? (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-12 text-center">
              <h2 className="text-lg font-semibold text-white mb-2">No escalations</h2>
              <p className="text-sm text-gray-400">The queue is empty. All calls are being handled by AI.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {escalations.map(esc => (
                <div key={esc.id} className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <span className={`text-xs font-bold uppercase ${PRIORITY_COLORS[esc.priority]}`}>{esc.priority}</span>
                      <div>
                        <p className="text-sm text-white font-medium">{esc.caller_name || esc.call_id}</p>
                        <div className="flex items-center gap-3 text-xs text-gray-500 mt-0.5">
                          {esc.caller_number && <span>{esc.caller_number}</span>}
                          {esc.reason && <span>{esc.reason}</span>}
                          <span>{Math.round(esc.wait_time_seconds)}s wait</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 text-xs rounded-full capitalize ${STATUS_COLORS[esc.status]?.bg || 'bg-gray-800'} ${STATUS_COLORS[esc.status]?.text || 'text-gray-400'}`}>
                        {esc.status}
                      </span>
                      {esc.status === 'waiting' && (
                        <>
                          <button onClick={() => autoAssign(esc.id)} className="px-3 py-1 text-xs bg-vox-600/20 text-vox-300 hover:bg-vox-600/30 rounded-lg transition-colors">Auto-Assign</button>
                          <button onClick={() => resolveEsc(esc.id)} className="px-3 py-1 text-xs bg-green-900/30 text-green-400 hover:bg-green-900/50 rounded-lg transition-colors">Resolve</button>
                        </>
                      )}
                      {esc.status === 'assigned' && (
                        <button onClick={() => resolveEsc(esc.id)} className="px-3 py-1 text-xs bg-green-900/30 text-green-400 hover:bg-green-900/50 rounded-lg transition-colors">Resolve</button>
                      )}
                    </div>
                  </div>
                  {esc.ai_summary && (
                    <p className="text-xs text-gray-500 mt-2 bg-[#0f0a1e] rounded-lg p-2">AI Summary: {esc.ai_summary}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Forecasting & ROI Tab ────────────────────── */}
      {tab === 'forecast' && (
        <div>
          {/* Forecast Section */}
          <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5 mb-6">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Volume Forecast</h3>
            <div className="flex items-center gap-3 mb-4">
              <input
                type="date"
                value={forecastDate}
                onChange={e => setForecastDate(e.target.value)}
                className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm focus:outline-none focus:ring-2 focus:ring-vox-500"
              />
              <button onClick={generateForecast} className="px-4 py-2 bg-vox-600 hover:bg-vox-700 text-white rounded-lg text-sm font-medium transition-colors">
                Generate Forecast
              </button>
            </div>

            {forecasts.length > 0 && (
              <div>
                {/* Visual bar chart */}
                <div className="flex items-end gap-1 h-40 mb-4">
                  {forecasts.map(fc => {
                    const maxVol = Math.max(...forecasts.map(f => f.predicted_volume), 1);
                    const pct = (fc.predicted_volume / maxVol) * 100;
                    const aiPct = fc.predicted_volume > 0 ? (fc.predicted_ai_handled / fc.predicted_volume) * 100 : 0;
                    return (
                      <div key={fc.hour} className="flex-1 flex flex-col items-center" title={`${fc.hour}:00 — ${fc.predicted_volume} calls, ${fc.recommended_staff} staff`}>
                        <div className="w-full rounded-t relative overflow-hidden" style={{ height: `${pct}%`, minHeight: '2px' }}>
                          <div className="absolute bottom-0 w-full bg-vox-600/60" style={{ height: `${aiPct}%` }} />
                          <div className="absolute top-0 w-full bg-red-500/40" style={{ height: `${100 - aiPct}%` }} />
                        </div>
                        <span className="text-[9px] text-gray-500 mt-1">{fc.hour}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="flex items-center gap-4 text-xs text-gray-400">
                  <span className="flex items-center gap-1"><span className="w-3 h-3 bg-vox-600/60 rounded" /> AI Handled</span>
                  <span className="flex items-center gap-1"><span className="w-3 h-3 bg-red-500/40 rounded" /> Escalated</span>
                </div>

                {/* Staffing table for peak hours */}
                <div className="mt-4">
                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Peak Hour Staffing</h4>
                  <div className="grid grid-cols-4 gap-2">
                    {forecasts.filter(f => f.predicted_volume > 20).map(fc => (
                      <div key={fc.hour} className="bg-[#0f0a1e] rounded-lg p-2 text-center">
                        <p className="text-xs text-gray-500">{fc.hour}:00</p>
                        <p className="text-lg font-bold text-white">{fc.recommended_staff}</p>
                        <p className="text-[10px] text-gray-500">{fc.predicted_volume} calls</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* ROI Calculator */}
          <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">ROI Calculator</h3>
            <div className="grid grid-cols-4 gap-3 mb-4">
              <div>
                <label className="text-xs text-gray-500 block mb-1">Monthly Calls</label>
                <input type="number" value={roiParams.total_monthly_calls} onChange={e => setRoiParams({ ...roiParams, total_monthly_calls: Number(e.target.value) })} className="w-full px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm focus:outline-none focus:ring-2 focus:ring-vox-500" />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Containment Rate %</label>
                <input type="number" value={roiParams.containment_rate} onChange={e => setRoiParams({ ...roiParams, containment_rate: Number(e.target.value) })} className="w-full px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm focus:outline-none focus:ring-2 focus:ring-vox-500" />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Human Agent $/hr</label>
                <input type="number" value={roiParams.human_agent_hourly_rate_cents / 100} onChange={e => setRoiParams({ ...roiParams, human_agent_hourly_rate_cents: Number(e.target.value) * 100 })} className="w-full px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm focus:outline-none focus:ring-2 focus:ring-vox-500" />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Avg Call (min)</label>
                <input type="number" value={roiParams.avg_call_duration_minutes} onChange={e => setRoiParams({ ...roiParams, avg_call_duration_minutes: Number(e.target.value) })} className="w-full px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm focus:outline-none focus:ring-2 focus:ring-vox-500" />
              </div>
            </div>
            <button onClick={calculateROI} className="px-4 py-2 bg-vox-600 hover:bg-vox-700 text-white rounded-lg text-sm font-medium transition-colors mb-4">
              Calculate ROI
            </button>

            {roi && (
              <div className="grid grid-cols-3 gap-4 mt-4">
                <div className="bg-[#0f0a1e] rounded-xl p-4 text-center">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Human-Only Cost</p>
                  <p className="text-xl font-bold text-red-400 mt-1">${(roi.human_cost_per_month_cents / 100).toLocaleString()}/mo</p>
                </div>
                <div className="bg-[#0f0a1e] rounded-xl p-4 text-center">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">AI Hybrid Cost</p>
                  <p className="text-xl font-bold text-vox-400 mt-1">${(roi.ai_cost_per_month_cents / 100).toLocaleString()}/mo</p>
                </div>
                <div className="bg-[#0f0a1e] rounded-xl p-4 text-center border border-green-900/50">
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Monthly Savings</p>
                  <p className="text-xl font-bold text-green-400 mt-1">${(roi.monthly_savings_cents / 100).toLocaleString()}/mo</p>
                  <p className="text-xs text-green-400 mt-1">{roi.savings_percentage.toFixed(1)}% reduction</p>
                </div>
              </div>
            )}
            {roi && (
              <div className="mt-4 bg-[#0f0a1e] rounded-xl p-4 text-center">
                <p className="text-xs text-gray-500 uppercase tracking-wider">Annual Savings</p>
                <p className="text-3xl font-bold text-green-400 mt-1">${(roi.annual_savings_cents / 100).toLocaleString()}</p>
                <p className="text-xs text-gray-500 mt-1">At {(roi.containment_rate * 100).toFixed(0)}% AI containment with {roi.calls_per_month.toLocaleString()} calls/month</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
