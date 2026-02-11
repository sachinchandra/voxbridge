import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useAuth } from '../context/AuthContext';
import { usageApi, keysApi } from '../services/api';
import { UsageSummary, ApiKey } from '../types';

export default function Dashboard() {
  const { customer } = useAuth();
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      usageApi.getSummary().catch(() => null),
      keysApi.list().catch(() => []),
    ]).then(([u, k]) => {
      setUsage(u);
      setKeys(k);
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

  const usagePercent = usage
    ? Math.min(100, (usage.total_minutes / usage.plan_minutes_limit) * 100)
    : 0;

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Dashboard</h1>
      <p className="text-gray-400 mb-8">Welcome back, {customer?.name || customer?.email}</p>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <StatsCard
          label="Minutes Used"
          value={usage?.total_minutes.toFixed(1) || '0'}
          sub={`of ${usage?.plan_minutes_limit || 100} min`}
        />
        <StatsCard
          label="Total Calls"
          value={String(usage?.total_calls || 0)}
          sub="this period"
        />
        <StatsCard
          label="Active Keys"
          value={String(keys.filter(k => k.status === 'active').length)}
          sub={`of ${keys.length} total`}
        />
        <StatsCard
          label="Minutes Left"
          value={usage?.minutes_remaining.toFixed(1) || '0'}
          sub={`${customer?.plan?.toUpperCase()} plan`}
          highlight={usagePercent > 80}
        />
      </div>

      {/* Usage bar */}
      <div className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50 mb-8">
        <div className="flex justify-between items-center mb-3">
          <h3 className="text-sm font-medium text-gray-300">Usage This Period</h3>
          <span className="text-sm text-gray-400">{usagePercent.toFixed(0)}%</span>
        </div>
        <div className="w-full h-3 bg-[#0f0a1e] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              usagePercent > 90 ? 'bg-red-500' : usagePercent > 70 ? 'bg-amber-500' : 'bg-vox-500'
            }`}
            style={{ width: `${usagePercent}%` }}
          />
        </div>
      </div>

      {/* Chart */}
      {usage && usage.daily_usage.length > 0 && (
        <div className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50 mb-8">
          <h3 className="text-sm font-medium text-gray-300 mb-4">Daily Usage (minutes)</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={usage.daily_usage}>
                <defs>
                  <linearGradient id="colorMinutes" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#7c3aed" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2040" />
                <XAxis
                  dataKey="date"
                  stroke="#6b7280"
                  fontSize={12}
                  tickFormatter={(v) => v.slice(5)}
                />
                <YAxis stroke="#6b7280" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    background: '#1a1230',
                    border: '1px solid #3b0f7a',
                    borderRadius: '8px',
                    color: '#f3f0ff',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="minutes"
                  stroke="#7c3aed"
                  fillOpacity={1}
                  fill="url(#colorMinutes)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Quick actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Link
          to="/dashboard/keys"
          className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50 hover:border-vox-600/50 transition-colors group"
        >
          <h3 className="text-white font-medium mb-1 group-hover:text-vox-300 transition-colors">Manage API Keys</h3>
          <p className="text-sm text-gray-400">Create and manage your SDK authentication keys</p>
        </Link>
        <Link
          to="/dashboard/billing"
          className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50 hover:border-vox-600/50 transition-colors group"
        >
          <h3 className="text-white font-medium mb-1 group-hover:text-vox-300 transition-colors">Upgrade Plan</h3>
          <p className="text-sm text-gray-400">Get more minutes and concurrent calls</p>
        </Link>
      </div>
    </div>
  );
}

function StatsCard({ label, value, sub, highlight }: {
  label: string; value: string; sub: string; highlight?: boolean;
}) {
  return (
    <div className="bg-[#1a1230] rounded-xl p-5 border border-vox-900/50">
      <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${highlight ? 'text-amber-400' : 'text-white'}`}>
        {value}
      </p>
      <p className="text-xs text-gray-500 mt-1">{sub}</p>
    </div>
  );
}
