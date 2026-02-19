import React, { useEffect, useState } from 'react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { qaApi } from '../services/api';
import { AnalyticsDetail } from '../types';

const COLORS = ['#7c3aed', '#10b981', '#f59e0b', '#ef4444', '#3b82f6', '#8b5cf6'];
const SENTIMENT_COLORS = ['#10b981', '#6b7280', '#ef4444'];

export default function Analytics() {
  const [analytics, setAnalytics] = useState<AnalyticsDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    qaApi.getAnalytics()
      .then(setAnalytics)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-vox-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  if (!analytics) {
    return <div className="text-center py-16 text-gray-400">Failed to load analytics</div>;
  }

  const humanCostPerMin = 0.50;
  const totalMinutes = analytics.total_calls > 0
    ? (analytics.avg_duration_seconds * analytics.total_calls) / 60
    : 0;
  const humanCost = totalMinutes * humanCostPerMin;
  const aiCost = analytics.total_cost_dollars;
  const savings = humanCost - aiCost;

  const sentimentData = [
    { name: 'Positive', value: analytics.sentiment_positive },
    { name: 'Neutral', value: analytics.sentiment_neutral },
    { name: 'Negative', value: analytics.sentiment_negative },
  ].filter(d => d.value > 0);

  const pieData = [
    { name: 'AI Handled', value: analytics.ai_handled },
    { name: 'Escalated', value: analytics.escalated },
  ].filter(d => d.value > 0);

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Analytics</h1>
      <p className="text-gray-400 mb-8">AI contact center performance overview</p>

      {/* Top KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <KpiCard label="Total Calls" value={String(analytics.total_calls)} />
        <KpiCard label="AI Containment" value={`${analytics.containment_rate}%`} highlight={true} />
        <KpiCard label="Avg Duration" value={`${Math.round(analytics.avg_duration_seconds)}s`} />
        <KpiCard label="AI Cost" value={`$${aiCost.toFixed(2)}`} />
        <KpiCard label="Est. Savings" value={`$${savings > 0 ? savings.toFixed(0) : '0'}`} highlight={savings > 0} />
      </div>

      {/* Row 1: Calls trend + AI vs Human pie */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-2 bg-[#1a1230] rounded-xl p-6 border border-vox-900/50">
          <h3 className="text-sm font-medium text-gray-300 mb-4">Calls Per Day</h3>
          {analytics.calls_by_day.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={analytics.calls_by_day}>
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

      {/* Row 2: Sentiment + Peak Hours */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Sentiment breakdown */}
        <div className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50">
          <h3 className="text-sm font-medium text-gray-300 mb-4">Caller Sentiment</h3>
          {sentimentData.length > 0 ? (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={sentimentData} cx="50%" cy="50%" innerRadius={45} outerRadius={75} dataKey="value" label={({ name, percent }: any) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}>
                    {sentimentData.map((_, i) => (
                      <Cell key={i} fill={SENTIMENT_COLORS[i % SENTIMENT_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#1a1230', border: '1px solid #3b0f7a', borderRadius: '8px', color: '#f3f0ff' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-56 flex items-center justify-center text-gray-500 text-sm">No sentiment data</div>
          )}
        </div>

        {/* Peak hours */}
        <div className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50">
          <h3 className="text-sm font-medium text-gray-300 mb-4">Calls by Hour</h3>
          {analytics.calls_by_hour.some(h => h.calls > 0) ? (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={analytics.calls_by_hour}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2040" />
                  <XAxis dataKey="hour" stroke="#6b7280" fontSize={10} tickFormatter={(v) => `${v}h`} />
                  <YAxis stroke="#6b7280" fontSize={10} />
                  <Tooltip
                    contentStyle={{ background: '#1a1230', border: '1px solid #3b0f7a', borderRadius: '8px', color: '#f3f0ff' }}
                    labelFormatter={(v) => `${v}:00`}
                  />
                  <Bar dataKey="calls" fill="#3b82f6" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-56 flex items-center justify-center text-gray-500 text-sm">No hourly data</div>
          )}
        </div>
      </div>

      {/* Row 3: Agent Leaderboard + Escalation Reasons */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Agent leaderboard */}
        <div className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50">
          <h3 className="text-sm font-medium text-gray-300 mb-4">Agent Leaderboard</h3>
          {analytics.agent_rankings.length > 0 ? (
            <div className="space-y-3">
              {analytics.agent_rankings.map((agent, i) => (
                <div key={agent.agent_id} className="flex items-center gap-3 bg-[#0f0a1e] rounded-lg p-3">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                    i === 0 ? 'bg-amber-600 text-white' :
                    i === 1 ? 'bg-gray-400 text-white' :
                    i === 2 ? 'bg-amber-800 text-white' :
                    'bg-gray-700 text-gray-300'
                  }`}>
                    {i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">{agent.agent_name}</p>
                    <p className="text-xs text-gray-500">{agent.calls} calls · {agent.containment_rate}% AI</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold text-vox-400">{agent.containment_rate}%</p>
                    <p className="text-xs text-gray-500">containment</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500 text-sm">No agent data yet</div>
          )}
        </div>

        {/* Escalation reasons */}
        <div className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50">
          <h3 className="text-sm font-medium text-gray-300 mb-4">Escalation Reasons</h3>
          {analytics.escalation_reasons.length > 0 ? (
            <div className="space-y-3">
              {analytics.escalation_reasons.map((item) => (
                <div key={item.reason} className="flex items-center gap-3">
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-gray-300 capitalize">{item.reason}</span>
                      <span className="text-xs text-gray-500">{item.count}</span>
                    </div>
                    <div className="h-1.5 bg-[#0f0a1e] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-red-500/60 rounded-full"
                        style={{ width: `${Math.min(100, (item.count / (analytics.escalated || 1)) * 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500 text-sm">No escalations yet</div>
          )}

          {/* Resolution breakdown */}
          <div className="mt-6 pt-4 border-t border-vox-900/30">
            <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-3">Resolution Breakdown</h4>
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-[#0f0a1e] rounded-lg p-3 text-center">
                <p className="text-lg font-bold text-emerald-400">{analytics.resolved}</p>
                <p className="text-xs text-gray-500">Resolved</p>
              </div>
              <div className="bg-[#0f0a1e] rounded-lg p-3 text-center">
                <p className="text-lg font-bold text-amber-400">{analytics.escalated}</p>
                <p className="text-xs text-gray-500">Escalated</p>
              </div>
              <div className="bg-[#0f0a1e] rounded-lg p-3 text-center">
                <p className="text-lg font-bold text-red-400">{analytics.abandoned}</p>
                <p className="text-xs text-gray-500">Abandoned</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Row 4: Cost savings */}
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
