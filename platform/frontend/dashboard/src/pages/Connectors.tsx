import React, { useState, useEffect } from 'react';
import { connectorsApi } from '../services/api';
import { ConnectorItem, ConnectorEvent } from '../types';

const TYPE_LABELS: Record<string, string> = {
  genesys: 'Genesys Cloud',
  amazon_connect: 'Amazon Connect',
  avaya: 'Avaya',
  cisco: 'Cisco UCCX',
  twilio: 'Twilio',
  five9: 'Five9',
  generic_sip: 'Generic SIP',
};

const STATUS_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  active: { bg: 'bg-green-900/30', text: 'text-green-400', dot: 'bg-green-500' },
  inactive: { bg: 'bg-gray-900/30', text: 'text-gray-400', dot: 'bg-gray-500' },
  error: { bg: 'bg-red-900/30', text: 'text-red-400', dot: 'bg-red-500' },
  configuring: { bg: 'bg-amber-900/30', text: 'text-amber-400', dot: 'bg-amber-500' },
};

export default function Connectors() {
  const [connectors, setConnectors] = useState<ConnectorItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [events, setEvents] = useState<ConnectorEvent[]>([]);

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [newConn, setNewConn] = useState({ name: '', connector_type: 'twilio', config: '{}' });

  const fetchData = async () => {
    try {
      const data = await connectorsApi.list();
      setConnectors(data);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const fetchEvents = async (connId: string) => {
    try {
      const data = await connectorsApi.getEvents(connId, 20);
      setEvents(data);
    } catch {}
  };

  const selectConnector = (connId: string) => {
    setSelectedId(connId === selectedId ? null : connId);
    if (connId !== selectedId) fetchEvents(connId);
  };

  const createConnector = async () => {
    if (!newConn.name) return;
    try {
      let config = {};
      try { config = JSON.parse(newConn.config); } catch {}
      await connectorsApi.create({
        name: newConn.name,
        connector_type: newConn.connector_type,
        config,
      });
      setNewConn({ name: '', connector_type: 'twilio', config: '{}' });
      setShowCreate(false);
      fetchData();
    } catch {}
  };

  const activateConnector = async (connId: string) => {
    try {
      await connectorsApi.activate(connId);
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Activation failed — check config');
    }
  };

  const deactivateConnector = async (connId: string) => {
    try {
      await connectorsApi.deactivate(connId);
      fetchData();
    } catch {}
  };

  const deleteConnector = async (connId: string) => {
    try {
      await connectorsApi.delete(connId);
      if (selectedId === connId) setSelectedId(null);
      fetchData();
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
          <h1 className="text-2xl font-bold text-white">Connectors</h1>
          <p className="text-sm text-gray-400 mt-1">Integrate with existing contact center platforms</p>
        </div>
        <button onClick={() => setShowCreate(!showCreate)} className="px-4 py-2 bg-vox-600 hover:bg-vox-700 text-white rounded-lg text-sm font-medium transition-colors">
          + New Connector
        </button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total Connectors', value: connectors.length, color: 'text-white' },
          { label: 'Active', value: connectors.filter(c => c.status === 'active').length, color: 'text-green-400' },
          { label: 'Errors', value: connectors.filter(c => c.status === 'error').length, color: connectors.some(c => c.status === 'error') ? 'text-red-400' : 'text-gray-400' },
          { label: 'Calls Routed', value: connectors.reduce((sum, c) => sum + c.total_calls_routed, 0), color: 'text-vox-400' },
        ].map(kpi => (
          <div key={kpi.label} className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-4 text-center">
            <p className="text-xs text-gray-500 uppercase tracking-wider">{kpi.label}</p>
            <p className={`text-2xl font-bold mt-1 ${kpi.color}`}>{kpi.value}</p>
          </div>
        ))}
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5 mb-6">
          <h3 className="text-sm font-semibold text-white mb-3">New Connector</h3>
          <div className="grid grid-cols-3 gap-3">
            <input value={newConn.name} onChange={e => setNewConn({ ...newConn, name: e.target.value })} placeholder="Connector name" className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500" />
            <select value={newConn.connector_type} onChange={e => setNewConn({ ...newConn, connector_type: e.target.value })} className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm focus:outline-none focus:ring-2 focus:ring-vox-500">
              {Object.entries(TYPE_LABELS).map(([val, label]) => (
                <option key={val} value={val}>{label}</option>
              ))}
            </select>
            <input value={newConn.config} onChange={e => setNewConn({ ...newConn, config: e.target.value })} placeholder='Config JSON e.g. {"account_sid":"..."}' className="px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-vox-500" />
          </div>
          <div className="flex justify-end mt-3 gap-2">
            <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">Cancel</button>
            <button onClick={createConnector} className="px-4 py-2 bg-vox-600 hover:bg-vox-700 text-white rounded-lg text-sm font-medium transition-colors">Create</button>
          </div>
        </div>
      )}

      {/* Connectors list */}
      {connectors.length === 0 ? (
        <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-12 text-center">
          <div className="w-16 h-16 rounded-2xl bg-vox-600/20 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-vox-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-white mb-2">No connectors yet</h2>
          <p className="text-sm text-gray-400 mb-6">Connect your existing contact center platform to gradually migrate calls to VoxBridge.</p>
          <button onClick={() => setShowCreate(true)} className="px-6 py-3 bg-vox-600 hover:bg-vox-700 text-white rounded-lg font-medium transition-colors">
            Add First Connector
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {connectors.map(conn => {
            const st = STATUS_COLORS[conn.status] || STATUS_COLORS.inactive;
            const isSelected = selectedId === conn.id;
            return (
              <div key={conn.id} className="bg-[#1a1230] rounded-xl border border-vox-900/50">
                <div className="p-4 cursor-pointer" onClick={() => selectConnector(conn.id)}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`w-3 h-3 rounded-full ${st.dot}`} />
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium text-white">{conn.name}</p>
                          <span className={`px-2 py-0.5 text-xs rounded-full ${st.bg} ${st.text}`}>{conn.status}</span>
                          <span className="text-xs text-gray-500">{TYPE_LABELS[conn.connector_type] || conn.connector_type}</span>
                        </div>
                        <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
                          <span>{conn.total_calls_routed} calls routed</span>
                          {conn.last_active_at && <span>Last active: {new Date(conn.last_active_at).toLocaleString()}</span>}
                          {conn.error_message && <span className="text-red-400">{conn.error_message}</span>}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {conn.status !== 'active' && (
                        <button onClick={e => { e.stopPropagation(); activateConnector(conn.id); }} className="px-3 py-1 text-xs bg-green-900/30 text-green-400 hover:bg-green-900/50 rounded-lg transition-colors">
                          Activate
                        </button>
                      )}
                      {conn.status === 'active' && (
                        <button onClick={e => { e.stopPropagation(); deactivateConnector(conn.id); }} className="px-3 py-1 text-xs bg-gray-800 text-gray-400 hover:bg-gray-700 rounded-lg transition-colors">
                          Deactivate
                        </button>
                      )}
                      <button onClick={e => { e.stopPropagation(); deleteConnector(conn.id); }} className="text-gray-600 hover:text-red-400 transition-colors">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>

                {/* Expanded detail */}
                {isSelected && (
                  <div className="border-t border-vox-900/30 p-4">
                    <div className="grid grid-cols-2 gap-6">
                      {/* Config */}
                      <div>
                        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Configuration</h4>
                        <pre className="text-xs text-gray-300 bg-[#0f0a1e] rounded-lg p-3 overflow-auto max-h-40">
                          {JSON.stringify(conn.config, null, 2)}
                        </pre>
                        {Object.keys(conn.department_mappings).length > 0 && (
                          <>
                            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mt-3 mb-2">Queue Mappings</h4>
                            <div className="space-y-1">
                              {Object.entries(conn.department_mappings).map(([queue, dept]) => (
                                <div key={queue} className="flex items-center gap-2 text-xs">
                                  <span className="text-gray-400">{queue}</span>
                                  <span className="text-gray-600">-&gt;</span>
                                  <span className="text-vox-400">{dept}</span>
                                </div>
                              ))}
                            </div>
                          </>
                        )}
                      </div>

                      {/* Events */}
                      <div>
                        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Recent Events</h4>
                        {events.length === 0 ? (
                          <p className="text-xs text-gray-500">No events recorded.</p>
                        ) : (
                          <div className="space-y-1 max-h-48 overflow-auto">
                            {events.map(ev => (
                              <div key={ev.id} className="flex items-start gap-2 text-xs">
                                <span className="text-gray-600 shrink-0">{new Date(ev.created_at).toLocaleTimeString()}</span>
                                <span className="px-1.5 py-0.5 rounded bg-white/5 text-gray-400 shrink-0">{ev.event_type}</span>
                                <span className="text-gray-300">{ev.message}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
