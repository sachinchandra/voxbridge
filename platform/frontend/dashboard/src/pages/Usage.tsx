import React, { useEffect, useState } from 'react';
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { usageApi } from '../services/api';
import { UsageSummary, UsageRecord } from '../types';

const COLORS = ['#7c3aed', '#06b6d4', '#f59e0b', '#ef4444', '#22c55e', '#ec4899', '#6366f1'];

export default function Usage() {
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [history, setHistory] = useState<UsageRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      usageApi.getSummary().catch(() => null),
      usageApi.getHistory(100).catch(() => []),
    ]).then(([s, h]) => {
      setSummary(s);
      setHistory(h);
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

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Usage Analytics</h1>
      <p className="text-gray-400 mb-8">Monitor your VoxBridge SDK usage</p>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-[#1a1230] rounded-xl p-5 border border-vox-900/50">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Total Minutes</p>
          <p className="text-3xl font-bold text-white mt-1">{summary?.total_minutes.toFixed(1) || '0'}</p>
          <p className="text-xs text-gray-500 mt-1">of {summary?.plan_minutes_limit || 100} limit</p>
        </div>
        <div className="bg-[#1a1230] rounded-xl p-5 border border-vox-900/50">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Total Calls</p>
          <p className="text-3xl font-bold text-white mt-1">{summary?.total_calls || 0}</p>
          <p className="text-xs text-gray-500 mt-1">this billing period</p>
        </div>
        <div className="bg-[#1a1230] rounded-xl p-5 border border-vox-900/50">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Avg. Call Duration</p>
          <p className="text-3xl font-bold text-white mt-1">
            {summary && summary.total_calls > 0
              ? ((summary.total_minutes / summary.total_calls) * 60).toFixed(0)
              : '0'}s
          </p>
          <p className="text-xs text-gray-500 mt-1">per call</p>
        </div>
      </div>

      {/* Daily usage chart */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-2 bg-[#1a1230] rounded-xl p-6 border border-vox-900/50">
          <h3 className="text-sm font-medium text-gray-300 mb-4">Daily Usage</h3>
          <div className="h-72">
            {summary && summary.daily_usage.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={summary.daily_usage}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2040" />
                  <XAxis dataKey="date" stroke="#6b7280" fontSize={12} tickFormatter={(v) => v.slice(5)} />
                  <YAxis stroke="#6b7280" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      background: '#1a1230',
                      border: '1px solid #3b0f7a',
                      borderRadius: '8px',
                      color: '#f3f0ff',
                    }}
                  />
                  <Bar dataKey="minutes" fill="#7c3aed" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500">
                No usage data yet
              </div>
            )}
          </div>
        </div>

        {/* Provider breakdown */}
        <div className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50">
          <h3 className="text-sm font-medium text-gray-300 mb-4">Provider Breakdown</h3>
          <div className="h-72">
            {summary && summary.provider_breakdown.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={summary.provider_breakdown}
                    dataKey="calls"
                    nameKey="provider"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ name, value }: any) => `${name}: ${value}`}
                  >
                    {summary.provider_breakdown.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: '#1a1230',
                      border: '1px solid #3b0f7a',
                      borderRadius: '8px',
                      color: '#f3f0ff',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500">
                No provider data yet
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent calls table */}
      <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 overflow-hidden">
        <div className="px-6 py-4 border-b border-vox-900/50">
          <h3 className="text-sm font-medium text-gray-300">Recent Calls</h3>
        </div>
        <table className="w-full">
          <thead>
            <tr className="border-b border-vox-900/30">
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wide">Session</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wide">Provider</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wide">Duration</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wide">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wide">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-vox-900/30">
            {history.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-gray-400">
                  No call history yet. Start using the SDK to see data here.
                </td>
              </tr>
            ) : (
              history.map((record) => (
                <tr key={record.id} className="hover:bg-white/[0.02]">
                  <td className="px-6 py-3 text-sm font-mono text-gray-300">
                    {record.session_id.slice(0, 8)}...
                  </td>
                  <td className="px-6 py-3 text-sm text-white">{record.provider || '-'}</td>
                  <td className="px-6 py-3 text-sm text-white">
                    {record.duration_seconds > 60
                      ? `${(record.duration_seconds / 60).toFixed(1)} min`
                      : `${record.duration_seconds.toFixed(0)}s`}
                  </td>
                  <td className="px-6 py-3">
                    <span className={`inline-flex px-2 py-1 text-xs rounded-full font-medium ${
                      record.status === 'completed'
                        ? 'bg-emerald-500/10 text-emerald-400'
                        : record.status === 'error'
                        ? 'bg-red-500/10 text-red-400'
                        : 'bg-amber-500/10 text-amber-400'
                    }`}>
                      {record.status}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-sm text-gray-400">
                    {new Date(record.created_at).toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
