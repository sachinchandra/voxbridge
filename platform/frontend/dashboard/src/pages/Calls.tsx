import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { callsApi, agentsApi } from '../services/api';
import { CallRecord, AgentListItem, CallsOverview } from '../types';

const statusColors: Record<string, string> = {
  completed: 'bg-emerald-600/20 text-emerald-300',
  in_progress: 'bg-blue-600/20 text-blue-300',
  initiated: 'bg-gray-600/20 text-gray-300',
  failed: 'bg-red-600/20 text-red-300',
  no_answer: 'bg-amber-600/20 text-amber-300',
  busy: 'bg-amber-600/20 text-amber-300',
  ringing: 'bg-blue-600/20 text-blue-300',
};

export default function Calls() {
  const navigate = useNavigate();
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [agents, setAgents] = useState<AgentListItem[]>([]);
  const [overview, setOverview] = useState<CallsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [filterAgent, setFilterAgent] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterDirection, setFilterDirection] = useState('');
  const limit = 20;

  const fetchCalls = useCallback((offset: number) => {
    const params: any = { limit, offset };
    if (filterAgent) params.agent_id = filterAgent;
    if (filterStatus) params.status = filterStatus;
    if (filterDirection) params.direction = filterDirection;

    callsApi.list(params).then((res) => {
      setCalls(res.calls);
      setTotal(res.total);
    }).catch(() => setCalls([]));
  }, [filterAgent, filterStatus, filterDirection, limit]);

  useEffect(() => {
    Promise.all([
      agentsApi.list().catch(() => []),
      callsApi.getOverview().catch(() => null),
    ]).then(([a, o]) => {
      setAgents(a);
      setOverview(o);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    fetchCalls(page * limit);
  }, [page, fetchCalls]);

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-vox-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Call Logs</h1>
      <p className="text-gray-400 mb-8">View and search all calls across your AI agents</p>

      {/* Overview stats */}
      {overview && overview.total_calls > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          <OverviewCard label="Total Calls" value={String(overview.total_calls)} />
          <OverviewCard label="AI Handled" value={String(overview.ai_handled)} />
          <OverviewCard label="Escalated" value={String(overview.escalated)} />
          <OverviewCard label="Containment" value={`${overview.containment_rate}%`} highlight={overview.containment_rate >= 80} />
          <OverviewCard label="Total Cost" value={`$${overview.total_cost_dollars.toFixed(2)}`} />
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <select
          value={filterAgent}
          onChange={(e) => { setFilterAgent(e.target.value); setPage(0); }}
          className="px-3 py-2 rounded-lg bg-[#1a1230] border border-vox-900/50 text-sm text-white focus:border-vox-500 focus:outline-none"
        >
          <option value="">All Agents</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>

        <select
          value={filterStatus}
          onChange={(e) => { setFilterStatus(e.target.value); setPage(0); }}
          className="px-3 py-2 rounded-lg bg-[#1a1230] border border-vox-900/50 text-sm text-white focus:border-vox-500 focus:outline-none"
        >
          <option value="">All Statuses</option>
          <option value="completed">Completed</option>
          <option value="in_progress">In Progress</option>
          <option value="failed">Failed</option>
          <option value="no_answer">No Answer</option>
        </select>

        <select
          value={filterDirection}
          onChange={(e) => { setFilterDirection(e.target.value); setPage(0); }}
          className="px-3 py-2 rounded-lg bg-[#1a1230] border border-vox-900/50 text-sm text-white focus:border-vox-500 focus:outline-none"
        >
          <option value="">All Directions</option>
          <option value="inbound">Inbound</option>
          <option value="outbound">Outbound</option>
        </select>

        {(filterAgent || filterStatus || filterDirection) && (
          <button
            onClick={() => { setFilterAgent(''); setFilterStatus(''); setFilterDirection(''); setPage(0); }}
            className="text-xs text-gray-400 hover:text-white transition-colors"
          >
            Clear filters
          </button>
        )}

        <div className="flex-1 text-right text-sm text-gray-500">
          {total} total calls
        </div>
      </div>

      {/* Calls table */}
      {calls.length === 0 ? (
        <div className="bg-[#1a1230] rounded-xl p-12 border border-vox-900/50 text-center">
          <p className="text-gray-400">No calls found</p>
        </div>
      ) : (
        <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-vox-900/50">
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">Agent</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">Direction</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">From / To</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">Duration</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">Status</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">Escalated</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">Cost</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">Time</th>
                </tr>
              </thead>
              <tbody>
                {calls.map((call) => (
                  <tr
                    key={call.id}
                    onClick={() => navigate(`/dashboard/calls/${call.id}`)}
                    className="border-b border-vox-900/30 hover:bg-white/[0.02] cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-4 text-white font-medium">{call.agent_name}</td>
                    <td className="py-3 px-4">
                      <span className={`inline-flex items-center gap-1 text-xs ${call.direction === 'inbound' ? 'text-blue-300' : 'text-emerald-300'}`}>
                        <svg className={`w-3 h-3 ${call.direction === 'inbound' ? '' : 'rotate-180'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                        </svg>
                        {call.direction}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-gray-300 text-xs font-mono">
                      {call.direction === 'inbound' ? call.from_number : call.to_number}
                    </td>
                    <td className="py-3 px-4 text-gray-300">{formatDuration(call.duration_seconds)}</td>
                    <td className="py-3 px-4">
                      <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${statusColors[call.status] || 'bg-gray-600/20 text-gray-300'}`}>
                        {call.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {call.escalated_to_human ? (
                        <span className="text-amber-300 text-xs">Yes</span>
                      ) : (
                        <span className="text-gray-500 text-xs">No</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-gray-300">${(call.cost_cents / 100).toFixed(2)}</td>
                    <td className="py-3 px-4 text-gray-400 text-xs">{formatTime(call.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {total > limit && (
            <div className="flex items-center justify-between p-4 border-t border-vox-900/50">
              <button
                onClick={() => setPage(Math.max(0, page - 1))}
                disabled={page === 0}
                className="px-3 py-1.5 rounded text-sm text-gray-400 hover:text-white disabled:opacity-30 transition-colors"
              >
                Previous
              </button>
              <span className="text-sm text-gray-500">
                Page {page + 1} of {Math.ceil(total / limit)}
              </span>
              <button
                onClick={() => setPage(page + 1)}
                disabled={(page + 1) * limit >= total}
                className="px-3 py-1.5 rounded text-sm text-gray-400 hover:text-white disabled:opacity-30 transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function OverviewCard({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="bg-[#1a1230] rounded-xl p-4 border border-vox-900/50">
      <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</p>
      <p className={`text-xl font-bold mt-1 ${highlight ? 'text-emerald-400' : 'text-white'}`}>{value}</p>
    </div>
  );
}
