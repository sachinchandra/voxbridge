import React, { useState, useEffect } from 'react';
import { complianceApi } from '../services/api';
import { ComplianceRuleItem, ComplianceViolationItem, ComplianceSummaryData, AuditLogEntryItem } from '../types';

const SEVERITY_COLORS: Record<string, { bg: string; text: string }> = {
  critical: { bg: 'bg-red-900/30', text: 'text-red-400' },
  warning: { bg: 'bg-amber-900/30', text: 'text-amber-400' },
  info: { bg: 'bg-blue-900/30', text: 'text-blue-400' },
};

const RULE_TYPE_LABELS: Record<string, string> = {
  pii_redaction: 'PII Redaction',
  script_adherence: 'Script Adherence',
  disclosure_required: 'Required Disclosures',
  forbidden_phrases: 'Forbidden Phrases',
  data_retention: 'Data Retention',
  hipaa: 'HIPAA',
  pci_dss: 'PCI DSS',
};

export default function Compliance() {
  const [summary, setSummary] = useState<ComplianceSummaryData | null>(null);
  const [rules, setRules] = useState<ComplianceRuleItem[]>([]);
  const [violations, setViolations] = useState<ComplianceViolationItem[]>([]);
  const [auditLog, setAuditLog] = useState<AuditLogEntryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'overview' | 'rules' | 'violations' | 'audit'>('overview');

  // Redact tool
  const [redactInput, setRedactInput] = useState('');
  const [redactOutput, setRedactOutput] = useState('');

  const fetchData = async () => {
    try {
      const [sum, r, v, a] = await Promise.all([
        complianceApi.getSummary(),
        complianceApi.listRules(),
        complianceApi.listViolations({ limit: 50 }),
        complianceApi.getAuditLog({ limit: 30 }),
      ]);
      setSummary(sum);
      setRules(r);
      setViolations(v);
      setAuditLog(a);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const createDefaults = async () => {
    try { await complianceApi.createDefaults(); fetchData(); } catch {}
  };

  const deleteRule = async (id: string) => {
    try { await complianceApi.deleteRule(id); fetchData(); } catch {}
  };

  const resolveViolation = async (id: string) => {
    try { await complianceApi.resolveViolation(id); fetchData(); } catch {}
  };

  const redactText = async () => {
    if (!redactInput.trim()) return;
    try {
      const result = await complianceApi.redactText(redactInput);
      setRedactOutput(result.redacted);
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
          <h1 className="text-2xl font-bold text-white">Compliance & Security</h1>
          <p className="text-sm text-gray-400 mt-1">PII redaction, compliance rules, audit trail, and violation tracking</p>
        </div>
      </div>

      {/* KPIs */}
      {summary && (
        <div className="grid grid-cols-5 gap-4 mb-6">
          {[
            { label: 'Rules', value: `${summary.enabled_rules}/${summary.total_rules}`, color: 'text-white' },
            { label: 'Violations', value: summary.total_violations, color: summary.total_violations > 0 ? 'text-red-400' : 'text-green-400' },
            { label: 'Unresolved', value: summary.unresolved_violations, color: summary.unresolved_violations > 0 ? 'text-amber-400' : 'text-green-400' },
            { label: 'Audit Entries', value: summary.audit_log_count, color: 'text-vox-400' },
            { label: 'Critical', value: summary.violations_by_severity?.critical || 0, color: (summary.violations_by_severity?.critical || 0) > 0 ? 'text-red-400' : 'text-green-400' },
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
        {(['overview', 'rules', 'violations', 'audit'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors capitalize ${tab === t ? 'bg-vox-600/20 text-vox-300' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}>
            {t}
          </button>
        ))}
      </div>

      {/* Overview tab */}
      {tab === 'overview' && (
        <div className="grid grid-cols-2 gap-6">
          {/* Violations by type */}
          <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Violations by Type</h3>
            {summary && Object.keys(summary.violations_by_type).length > 0 ? (
              <div className="space-y-2">
                {Object.entries(summary.violations_by_type).map(([type, count]) => (
                  <div key={type} className="flex items-center justify-between">
                    <span className="text-sm text-gray-300">{RULE_TYPE_LABELS[type] || type}</span>
                    <span className="text-sm font-semibold text-white">{count}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-500">No violations recorded.</p>
            )}
          </div>

          {/* PII Redaction tool */}
          <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">PII Redaction Tool</h3>
            <textarea value={redactInput} onChange={e => setRedactInput(e.target.value)} rows={3} placeholder="Paste text to redact PII (SSN, credit cards, etc.)..." className="w-full px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500 mb-2" />
            <button onClick={redactText} className="px-4 py-2 bg-vox-600 hover:bg-vox-700 text-white rounded-lg text-sm font-medium transition-colors mb-2">
              Redact
            </button>
            {redactOutput && (
              <div className="bg-[#0f0a1e] rounded-lg p-3 mt-2">
                <p className="text-xs text-gray-500 mb-1">Redacted:</p>
                <p className="text-sm text-green-400 font-mono">{redactOutput}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Rules tab */}
      {tab === 'rules' && (
        <div>
          {rules.length === 0 ? (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-8 text-center">
              <p className="text-gray-400 text-sm mb-4">No compliance rules configured.</p>
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
                        <div className={`w-3 h-3 rounded-full ${rule.enabled ? 'bg-green-500' : 'bg-gray-600'}`} />
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium text-white">{rule.name}</p>
                            <span className={`px-2 py-0.5 text-xs rounded-full ${sev.bg} ${sev.text}`}>{rule.severity}</span>
                            <span className="text-xs text-gray-500">{RULE_TYPE_LABELS[rule.rule_type] || rule.rule_type}</span>
                          </div>
                          {rule.config && Object.keys(rule.config).length > 0 && (
                            <p className="text-xs text-gray-500 mt-1 font-mono">{JSON.stringify(rule.config).slice(0, 100)}</p>
                          )}
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

      {/* Violations tab */}
      {tab === 'violations' && (
        <div>
          {violations.length === 0 ? (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-8 text-center">
              <p className="text-gray-400 text-sm">No compliance violations found. Your calls are clean!</p>
            </div>
          ) : (
            <div className="space-y-3">
              {violations.map(v => {
                const sev = SEVERITY_COLORS[v.severity] || SEVERITY_COLORS.info;
                return (
                  <div key={v.id} className={`bg-[#1a1230] rounded-xl border border-vox-900/50 p-4 ${v.resolved ? 'opacity-50' : ''}`}>
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 text-xs rounded-full ${sev.bg} ${sev.text}`}>{v.severity}</span>
                          <p className="text-sm font-medium text-white">{v.description}</p>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-gray-500 mt-1">
                          <span>Rule: {v.rule_name}</span>
                          <span>{RULE_TYPE_LABELS[v.rule_type] || v.rule_type}</span>
                          <span>{new Date(v.created_at).toLocaleString()}</span>
                          {v.resolved && <span className="text-green-400">Resolved</span>}
                        </div>
                        {v.transcript_excerpt && (
                          <p className="text-xs text-gray-400 mt-1 font-mono">{v.transcript_excerpt}</p>
                        )}
                      </div>
                      {!v.resolved && (
                        <button onClick={() => resolveViolation(v.id)} className="px-3 py-1 text-xs bg-green-900/30 text-green-400 hover:bg-green-900/50 rounded-lg transition-colors">
                          Resolve
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Audit Log tab */}
      {tab === 'audit' && (
        <div>
          {auditLog.length === 0 ? (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-8 text-center">
              <p className="text-gray-400 text-sm">No audit log entries yet.</p>
            </div>
          ) : (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-vox-900/30 text-gray-500 uppercase tracking-wider">
                    <th className="text-left px-4 py-3">Time</th>
                    <th className="text-left px-4 py-3">Action</th>
                    <th className="text-left px-4 py-3">Resource</th>
                    <th className="text-left px-4 py-3">User</th>
                    <th className="text-left px-4 py-3">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {auditLog.map(entry => (
                    <tr key={entry.id} className="border-b border-vox-900/20 hover:bg-white/5">
                      <td className="px-4 py-3 text-gray-400">{new Date(entry.created_at).toLocaleString()}</td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded bg-vox-900/30 text-vox-400">{entry.action}</span>
                      </td>
                      <td className="px-4 py-3 text-gray-300">{entry.resource_type}{entry.resource_id ? `/${entry.resource_id.slice(0, 8)}` : ''}</td>
                      <td className="px-4 py-3 text-gray-400">{entry.user_email}</td>
                      <td className="px-4 py-3 text-gray-400">{entry.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
