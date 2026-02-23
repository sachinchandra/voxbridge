import React, { useState, useEffect } from 'react';
import { routingApi } from '../services/api';
import { Department, RoutingRule, RoutingResult } from '../types';

const MATCH_TYPE_LABELS: Record<string, string> = {
  keyword: 'Keyword',
  regex: 'Regex',
  dtmf: 'DTMF',
  intent_model: 'AI Model',
};

export default function Routing() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [rules, setRules] = useState<RoutingRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'departments' | 'rules' | 'test'>('departments');

  // Test state
  const [testText, setTestText] = useState('');
  const [testDtmf, setTestDtmf] = useState('');
  const [testResult, setTestResult] = useState<RoutingResult | null>(null);
  const [testing, setTesting] = useState(false);

  // Create dept form
  const [showCreate, setShowCreate] = useState(false);
  const [newDept, setNewDept] = useState({ name: '', description: '', keywords: '' });

  // Create rule form
  const [showCreateRule, setShowCreateRule] = useState(false);
  const [newRule, setNewRule] = useState({ name: '', department_id: '', match_type: 'keyword', match_value: '' });

  const fetchData = async () => {
    try {
      const [d, r] = await Promise.all([routingApi.listDepartments(), routingApi.listRules()]);
      setDepartments(d);
      setRules(r);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const createDefaults = async () => {
    try {
      await routingApi.createDefaults();
      fetchData();
    } catch {}
  };

  const createDept = async () => {
    if (!newDept.name) return;
    try {
      await routingApi.createDepartment({
        name: newDept.name,
        description: newDept.description,
        intent_keywords: newDept.keywords.split(',').map(k => k.trim()).filter(Boolean),
      });
      setNewDept({ name: '', description: '', keywords: '' });
      setShowCreate(false);
      fetchData();
    } catch {}
  };

  const deleteDept = async (id: string) => {
    try { await routingApi.deleteDepartment(id); fetchData(); } catch {}
  };

  const createRule = async () => {
    if (!newRule.name || !newRule.department_id) return;
    try {
      await routingApi.createRule({
        name: newRule.name,
        department_id: newRule.department_id,
        match_type: newRule.match_type,
        match_value: newRule.match_value,
      });
      setNewRule({ name: '', department_id: '', match_type: 'keyword', match_value: '' });
      setShowCreateRule(false);
      fetchData();
    } catch {}
  };

  const deleteRule = async (id: string) => {
    try { await routingApi.deleteRule(id); fetchData(); } catch {}
  };

  const testRoute = async () => {
    if (!testText && !testDtmf) return;
    setTesting(true);
    try {
      const result = await routingApi.classify(testText, testDtmf);
      setTestResult(result);
    } catch {}
    setTesting(false);
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
          <h1 className="text-2xl font-bold text-white">Routing</h1>
          <p className="text-sm text-gray-400 mt-1">Manage departments and route calls based on caller intent</p>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Departments', value: departments.length, color: 'text-white' },
          { label: 'Routing Rules', value: rules.length, color: 'text-vox-400' },
          { label: 'Default', value: departments.find(d => d.is_default)?.name || 'None', color: 'text-green-400' },
          { label: 'Active Depts', value: departments.filter(d => d.enabled).length, color: 'text-amber-400' },
        ].map(kpi => (
          <div key={kpi.label} className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-4 text-center">
            <p className="text-xs text-gray-500 uppercase tracking-wider">{kpi.label}</p>
            <p className={`text-2xl font-bold mt-1 ${kpi.color}`}>{kpi.value}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6">
        {(['departments', 'rules', 'test'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors capitalize ${tab === t ? 'bg-vox-600/20 text-vox-300' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}>
            {t === 'departments' ? `Departments (${departments.length})` : t === 'rules' ? `Rules (${rules.length})` : 'Test Router'}
          </button>
        ))}
      </div>

      {/* Departments tab */}
      {tab === 'departments' && (
        <div>
          {departments.length === 0 ? (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-8 text-center">
              <p className="text-gray-400 text-sm mb-4">No departments configured yet.</p>
              <button onClick={createDefaults} className="px-6 py-3 bg-vox-600 hover:bg-vox-700 text-white rounded-lg font-medium transition-colors">
                Create Default Departments
              </button>
            </div>
          ) : (
            <>
              <div className="flex justify-end mb-4">
                <button onClick={() => setShowCreate(!showCreate)} className="px-4 py-2 bg-vox-600 hover:bg-vox-700 text-white rounded-lg text-sm font-medium transition-colors">
                  + New Department
                </button>
              </div>

              {showCreate && (
                <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5 mb-4">
                  <h3 className="text-sm font-semibold text-white mb-3">New Department</h3>
                  <div className="grid grid-cols-3 gap-3">
                    <input value={newDept.name} onChange={e => setNewDept({ ...newDept, name: e.target.value })} placeholder="Department name" className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500" />
                    <input value={newDept.description} onChange={e => setNewDept({ ...newDept, description: e.target.value })} placeholder="Description" className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500" />
                    <input value={newDept.keywords} onChange={e => setNewDept({ ...newDept, keywords: e.target.value })} placeholder="Keywords (comma-separated)" className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500" />
                  </div>
                  <div className="flex justify-end mt-3 gap-2">
                    <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">Cancel</button>
                    <button onClick={createDept} className="px-4 py-2 bg-vox-600 hover:bg-vox-700 text-white rounded-lg text-sm font-medium transition-colors">Create</button>
                  </div>
                </div>
              )}

              <div className="space-y-3">
                {departments.map(dept => (
                  <div key={dept.id} className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${dept.enabled ? 'bg-green-500' : 'bg-gray-600'}`} />
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium text-white">{dept.name}</p>
                            {dept.is_default && <span className="px-2 py-0.5 text-xs rounded-full bg-green-900/50 text-green-400">Default</span>}
                            <span className="text-xs text-gray-500">Priority: {dept.priority}</span>
                          </div>
                          <p className="text-xs text-gray-400 mt-1">{dept.description || 'No description'}</p>
                          {dept.intent_keywords.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {dept.intent_keywords.map(kw => (
                                <span key={kw} className="px-2 py-0.5 text-[10px] rounded bg-vox-900/30 text-vox-400">{kw}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                      <button onClick={() => deleteDept(dept.id)} className="text-gray-600 hover:text-red-400 transition-colors">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* Rules tab */}
      {tab === 'rules' && (
        <div>
          <div className="flex justify-end mb-4">
            <button onClick={() => setShowCreateRule(!showCreateRule)} className="px-4 py-2 bg-vox-600 hover:bg-vox-700 text-white rounded-lg text-sm font-medium transition-colors">
              + New Rule
            </button>
          </div>

          {showCreateRule && (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5 mb-4">
              <h3 className="text-sm font-semibold text-white mb-3">New Routing Rule</h3>
              <div className="grid grid-cols-2 gap-3">
                <input value={newRule.name} onChange={e => setNewRule({ ...newRule, name: e.target.value })} placeholder="Rule name" className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500" />
                <select value={newRule.department_id} onChange={e => setNewRule({ ...newRule, department_id: e.target.value })} className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm focus:outline-none focus:ring-2 focus:ring-vox-500">
                  <option value="">Select department...</option>
                  {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
                <select value={newRule.match_type} onChange={e => setNewRule({ ...newRule, match_type: e.target.value })} className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm focus:outline-none focus:ring-2 focus:ring-vox-500">
                  <option value="keyword">Keyword</option>
                  <option value="regex">Regex</option>
                  <option value="dtmf">DTMF</option>
                </select>
                <input value={newRule.match_value} onChange={e => setNewRule({ ...newRule, match_value: e.target.value })} placeholder="Match value (e.g. buy,purchase)" className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500" />
              </div>
              <div className="flex justify-end mt-3 gap-2">
                <button onClick={() => setShowCreateRule(false)} className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">Cancel</button>
                <button onClick={createRule} className="px-4 py-2 bg-vox-600 hover:bg-vox-700 text-white rounded-lg text-sm font-medium transition-colors">Create</button>
              </div>
            </div>
          )}

          {rules.length === 0 ? (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-8 text-center">
              <p className="text-gray-400 text-sm">No routing rules configured. Create rules to route calls based on keywords, patterns, or DTMF input.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {rules.map(rule => {
                const dept = departments.find(d => d.id === rule.department_id);
                return (
                  <div key={rule.id} className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium text-white">{rule.name}</p>
                          <span className="px-2 py-0.5 text-xs rounded-full bg-blue-900/30 text-blue-400">{MATCH_TYPE_LABELS[rule.match_type] || rule.match_type}</span>
                          <span className="text-xs text-gray-500">Priority: {rule.priority}</span>
                        </div>
                        <p className="text-xs text-gray-400 mt-1">
                          Match: <span className="text-vox-400">{rule.match_value}</span> {dept && <>Route to: <span className="text-green-400">{dept.name}</span></>}
                        </p>
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

      {/* Test tab */}
      {tab === 'test' && (
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Test Call Router</h3>
            <p className="text-xs text-gray-400 mb-3">Enter what a caller might say or a DTMF digit to test which department gets selected.</p>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Caller speech</label>
                <textarea value={testText} onChange={e => setTestText(e.target.value)} rows={3} placeholder="e.g. I want to buy a plan..." className="w-full px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">DTMF digit (optional)</label>
                <input value={testDtmf} onChange={e => setTestDtmf(e.target.value)} placeholder="e.g. 1" className="w-full px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500" />
              </div>
              <button onClick={testRoute} disabled={testing} className="w-full px-4 py-2 bg-vox-600 hover:bg-vox-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors">
                {testing ? 'Routing...' : 'Test Route'}
              </button>
            </div>
          </div>

          <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Result</h3>
            {testResult ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">Department:</span>
                  <span className="text-sm font-semibold text-white">{testResult.department_name || 'None'}</span>
                  {testResult.fallback && <span className="px-2 py-0.5 text-xs rounded-full bg-amber-900/30 text-amber-400">Fallback</span>}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">Confidence:</span>
                  <span className={`text-sm font-semibold ${testResult.confidence >= 0.7 ? 'text-green-400' : testResult.confidence >= 0.3 ? 'text-amber-400' : 'text-red-400'}`}>
                    {(testResult.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                {testResult.matched_keywords && testResult.matched_keywords.length > 0 && (
                  <div>
                    <span className="text-xs text-gray-500 block mb-1">Matched:</span>
                    <div className="flex flex-wrap gap-1">
                      {testResult.matched_keywords.map((kw, i) => (
                        <span key={i} className="px-2 py-0.5 text-xs rounded bg-green-900/30 text-green-400">{kw}</span>
                      ))}
                    </div>
                  </div>
                )}
                {testResult.agent_id && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">Agent:</span>
                    <span className="text-xs text-vox-400">{testResult.agent_id}</span>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-gray-500">Run a test to see routing results.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
