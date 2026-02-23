import React, { useState, useEffect } from 'react';
import { alertsApi } from '../services/api';
import { AlertRule, AlertItem, AlertSummaryData } from '../types';

const SEVERITY_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  critical: { bg: 'bg-red-900/30', text: 'text-red-400', dot: 'bg-red-500' },
  warning: { bg: 'bg-amber-900/30', text: 'text-amber-400', dot: 'bg-amber-500' },
  info: { bg: 'bg-blue-900/30', text: 'text-blue-400', dot: 'bg-blue-500' },
};

const TYPE_LABELS: Record<string, string> = {
  high_volume: 'High Volume',
  angry_caller_spike: 'Angry Callers',
  low_quality_score: 'Low Quality',
  high_escalation_rate: 'High Escalation',
  pii_detected: 'PII Detected',
  agent_down: 'Agent Down',
  api_failure: 'API Failure',
  cost_threshold: 'Cost Limit',
};

export default function Alerts() {
  const [summary, setSummary] = useState<AlertSummaryData | null>(null);
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'alerts' | 'rules'>('alerts');

  const fetchData = async () => {
    try {
      const [s, r, a] = await Promise.all([
        alertsApi.getSummary(),
        alertsApi.listRules(),
        alertsApi.list(),
      ]);
      setSummary(s);
      setRules(r);
      setAlerts(a);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const createDefaults = async () => {
    try {
      await alertsApi.createDefaults();
      fetchData();
    } catch {}
  };

  const acknowledgeAlert = async (alertId: string) => {
    try {
      await alertsApi.acknowledge(alertId);
      setAlerts(alerts.map(a => a.id === alertId ? { ...a, acknowledged: true } : a));
      if (summary) {
        setSummary({ ...summary, unacknowledged: Math.max(0, summary.unacknowledged - 1) });
      }
    } catch {}
  };

  const acknowledgeAll = async () => {
    try {
      await alertsApi.acknowledgeAll();
      setAlerts(alerts.map(a => ({ ...a, acknowledged: true })));
      if (summary) setSummary({ ...summary, unacknowledged: 0 });
    } catch {}
  };

  const toggleRule = async (rule: AlertRule) => {
    try {
      await alertsApi.updateRule(rule.id, { enabled: !rule.enabled });
      setRules(rules.map(r => r.id === rule.id ? { ...r, enabled: !r.enabled } : r));
    } catch {}
  };

  const deleteRule = async (ruleId: string) => {
    try {
      await alertsApi.deleteRule(ruleId);
      setRules(rules.filter(r => r.id !== ruleId));
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
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Alerts</h1>
          <p className="text-sm text-gray-400 mt-1">Monitor call metrics and get notified when thresholds are exceeded</p>
        </div>
        <div className="flex items-center gap-2">
          {summary && summary.unacknowledged > 0 && (
            <button onClick={acknowledgeAll} className="px-4 py-2 text-sm bg-white/5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors">
              Acknowledge All ({summary.unacknowledged})
            </button>
          )}
        </div>
      </div>

      {/* Summary KPIs */}
      {summary && (
        <div className="grid grid-cols-5 gap-4 mb-6">
          {[
            { label: 'Total Alerts', value: summary.total, color: 'text-white' },
            { label: 'Unacknowledged', value: summary.unacknowledged, color: summary.unacknowledged > 0 ? 'text-amber-400' : 'text-gray-400' },
            { label: 'Critical', value: summary.critical, color: summary.critical > 0 ? 'text-red-400' : 'text-gray-400' },
            { label: 'Warning', value: summary.warning, color: summary.warning > 0 ? 'text-amber-400' : 'text-gray-400' },
            { label: 'Info', value: summary.info, color: 'text-blue-400' },
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
        {(['alerts', 'rules'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors ${tab === t ? 'bg-vox-600/20 text-vox-300' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}>
            {t === 'alerts' ? `Alerts (${alerts.length})` : `Rules (${rules.length})`}
          </button>
        ))}
      </div>

      {/* Alerts list */}
      {tab === 'alerts' && (
        <div className="space-y-3">
          {alerts.length === 0 ? (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-8 text-center">
              <p className="text-gray-400 text-sm">No alerts triggered yet. Set up rules to start monitoring.</p>
            </div>
          ) : (
            alerts.map(alert => {
              const sev = SEVERITY_COLORS[alert.severity] || SEVERITY_COLORS.info;
              return (
                <div key={alert.id} className={`bg-[#1a1230] rounded-xl border border-vox-900/50 p-4 ${!alert.acknowledged ? 'border-l-4 border-l-' + (alert.severity === 'critical' ? 'red' : alert.severity === 'warning' ? 'amber' : 'blue') + '-500' : 'opacity-60'}`}>
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <div className={`w-2 h-2 rounded-full mt-1.5 ${sev.dot}`} />
                      <div>
                        <p className="text-sm font-medium text-white">{alert.title}</p>
                        <p className="text-xs text-gray-400 mt-1">{alert.message}</p>
                        <div className="flex items-center gap-3 mt-2">
                          <span className={`px-2 py-0.5 text-xs rounded-full ${sev.bg} ${sev.text}`}>{alert.severity}</span>
                          <span className="text-xs text-gray-500">{TYPE_LABELS[alert.alert_type] || alert.alert_type}</span>
                          <span className="text-xs text-gray-600">{new Date(alert.created_at).toLocaleString()}</span>
                        </div>
                      </div>
                    </div>
                    {!alert.acknowledged && (
                      <button onClick={() => acknowledgeAlert(alert.id)} className="px-3 py-1 text-xs bg-white/5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors shrink-0">
                        Ack
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Rules list */}
      {tab === 'rules' && (
        <div>
          {rules.length === 0 ? (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-8 text-center">
              <p className="text-gray-400 text-sm mb-4">No alert rules configured yet.</p>
              <button onClick={createDefaults} className="px-6 py-3 bg-vox-600 hover:bg-vox-700 text-white rounded-lg font-medium transition-colors">
                Create Default Rules
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {rules.map(rule => {
                const sev = SEVERITY_COLORS[rule.severity] || SEVERITY_COLORS.info;
                return (
                  <div key={rule.id} className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <button onClick={() => toggleRule(rule)} className={`w-10 h-5 rounded-full relative transition-colors ${rule.enabled ? 'bg-vox-600' : 'bg-gray-700'}`}>
                          <div className={`w-4 h-4 rounded-full bg-white absolute top-0.5 transition-transform ${rule.enabled ? 'translate-x-5' : 'translate-x-0.5'}`} />
                        </button>
                        <div>
                          <p className={`text-sm font-medium ${rule.enabled ? 'text-white' : 'text-gray-500'}`}>{rule.name}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className={`px-2 py-0.5 text-xs rounded-full ${sev.bg} ${sev.text}`}>{rule.severity}</span>
                            <span className="text-xs text-gray-500">{TYPE_LABELS[rule.alert_type] || rule.alert_type}</span>
                            {rule.notify_email && <span className="text-xs text-gray-600">Email</span>}
                            {rule.config && Object.keys(rule.config).length > 0 && (
                              <span className="text-xs text-gray-600">
                                {Object.entries(rule.config).map(([k, v]) => `${k}: ${v}`).join(', ')}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <button onClick={() => deleteRule(rule.id)} className="text-gray-600 hover:text-red-400 transition-colors">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
