import React, { useEffect, useState } from 'react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { callsApi, agentsApi } from '../services/api';
import { AgentListItem, AgentStats, CallsOverview } from '../types';

const COLORS = ['#7c3aed', '#10b981', '#f59e0b', '#ef4444', '#3b82f6', '#8b5cf6'];

export default function Analytics() {
  const [overview, setOverview] = useState<CallsOverview | null>(null);
  const [agents, setAgents] = useState<AgentListItem[]>([]);
  const [agentStats, setAgentStats] = useState<Record<string, AgentStats>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      callsApi.getOverview().catch(() => null),
      agentsApi.list().catch(() => []),
    ]).then(async ([o, a]) => {
      setOverview(o);
      setAgents(a);

      // Fetch stats for each agent
      const statsMap: Record<string, AgentStats> = {};
      await Promise.all(
        a.slice(0, 10).map(async (agent: AgentListItem) => {
          try {
            const s = await agentsApi.getStats(agent.id);
            statsMap[agent.id] = s;
          } catch {}
        })
      );
      setAgentStats(statsMap);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-vox-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  // Aggregate calls by day across all agents
  const dailyMap: Record<string, number> = {};
  Object.values(agentStats).forEach((s) => {
    s.calls_by_day.forEach(({ date, calls }) => {
      dailyMap[date] = (dailyMap[date] || 0) + calls;
    });
  });
  const dailyCalls = Object.entries(dailyMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, calls]) => ({ date, calls }));

  // Agent comparison data
  const agentComparison = agents
    .filter((a) => agentStats[a.id])
    .map((a) => ({
      name: a.name.length > 15 ? a.name.slice(0, 15) + '...' : a.name,
      calls: agentStats[a.id].total_calls,
      containment: agentStats[a.id].containment_rate,
      avgDuration: Math.round(agentStats[a.id].avg_duration_seconds),
    }));

  // Direction breakdown for pie chart
  const pieData = [
    { name: 'AI Handled', value: overview?.ai_handled || 0 },
    { name: 'Escalated', value: overview?.escalated || 0 },
  ].filter((d) => d.value > 0);

  // Cost savings estimate
  const humanCostPerMin = 0.50; // avg $30/hr = $0.50/min
  const totalMinutes = overview ? (overview.avg_duration_seconds * overview.total_calls) / 60 : 0;
  const humanCost = totalMinutes * humanCostPerMin;
  const aiCost = (overview?.total_cost_cents || 0) / 100;
  const savings = humanCost - aiCost;

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Analytics</h1>
      <p className="text-gray-400 mb-8">AI contact center performance overview</p>

      {/* Top-level KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <KpiCard label="Total Calls" value={String(overview?.total_calls || 0)} />
        <KpiCard label="AI Containment" value={`${overview?.containment_rate || 0}%`} highlight={true} />
        <KpiCard label="Avg Duration" value={`${Math.round(overview?.avg_duration_seconds || 0)}s`} />
        <KpiCard label="AI Cost" value={`$${aiCost.toFixed(2)}`} />
        <KpiCard label="Est. Savings" value={`$${savings > 0 ? savings.toFixed(0) : '0'}`} highlight={savings > 0} />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Calls per day */}
        <div className="lg:col-span-2 bg-[#1a1230] rounded-xl p-6 border border-vox-900/50">
          <h3 className="text-sm font-medium text-gray-300 mb-4">Calls Per Day</h3>
          {dailyCalls.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={dailyCalls}>
                  <defs>
                    <linearGradient id="colorCalls" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#7c3aed" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2040" />
                  <XAxis dataKey="date" stroke="#6b7280" fontSize={11} tickFormatter={(v) => v.slice(5)} />
                  <YAxis stroke="#6b7280" fontSize={11} />
                  <Tooltip contentStyle={{ background: '#1a1230', border: '1px solid #3b0f7a', borderRadius: '8px', color: '#f3f0ff' }} />
                  <Area type="monotone" dataKey="calls" stroke="#7c3aed" fillOpacity={1} fill="url(#colorCalls)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500 text-sm">No call data yet</div>
          )}
        </div>

        {/* AI vs Escalated pie */}
        <div className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50">
          <h3 className="text-sm font-medium text-gray-300 mb-4">AI vs Human</h3>
          {pieData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" label={({ name, percent }: any) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}>
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#1a1230', border: '1px solid #3b0f7a', borderRadius: '8px', color: '#f3f0ff' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500 text-sm">No data yet</div>
          )}
        </div>
      </div>

      {/* Agent comparison */}
      {agentComparison.length > 0 && (
        <div className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50 mb-8">
          <h3 className="text-sm font-medium text-gray-300 mb-4">Agent Comparison — Calls</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={agentComparison}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2040" />
                <XAxis dataKey="name" stroke="#6b7280" fontSize={11} />
                <YAxis stroke="#6b7280" fontSize={11} />
                <Tooltip contentStyle={{ background: '#1a1230', border: '1px solid #3b0f7a', borderRadius: '8px', color: '#f3f0ff' }} />
                <Bar dataKey="calls" fill="#7c3aed" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Cost savings breakdown */}
      <div className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50">
        <h3 className="text-sm font-medium text-gray-300 mb-4">Cost Savings Estimate</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-[#0f0a1e] rounded-lg p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide">If Handled by Humans</p>
            <p className="text-xl font-bold text-red-400 mt-1">${humanCost.toFixed(2)}</p>
            <p className="text-xs text-gray-500 mt-1">{totalMinutes.toFixed(0)} min &times; $0.50/min</p>
          </div>
          <div className="bg-[#0f0a1e] rounded-lg p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide">AI Cost (Actual)</p>
            <p className="text-xl font-bold text-vox-400 mt-1">${aiCost.toFixed(2)}</p>
            <p className="text-xs text-gray-500 mt-1">{totalMinutes.toFixed(0)} min &times; $0.06/min</p>
          </div>
          <div className="bg-[#0f0a1e] rounded-lg p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide">You Saved</p>
            <p className="text-xl font-bold text-emerald-400 mt-1">${savings > 0 ? savings.toFixed(2) : '0.00'}</p>
            <p className="text-xs text-gray-500 mt-1">{savings > 0 ? `${((savings / humanCost) * 100).toFixed(0)}% reduction` : 'Start making calls!'}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function KpiCard({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="bg-[#1a1230] rounded-xl p-4 border border-vox-900/50">
      <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</p>
      <p className={`text-xl font-bold mt-1 ${highlight ? 'text-emerald-400' : 'text-white'}`}>{value}</p>
    </div>
  );
}
