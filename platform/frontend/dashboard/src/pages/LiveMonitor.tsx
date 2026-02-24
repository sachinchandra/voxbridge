import React, { useState, useEffect, useCallback, useRef } from 'react';
import { liveApi } from '../services/api';
import { useWS } from '../context/WebSocketContext';
import { LiveSnapshot, LiveEvent, ActiveCallItem, AgentPresenceItem } from '../types';

const EVENT_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  'call.started': { bg: 'bg-green-900/30', text: 'text-green-400', label: 'Call' },
  'call.ended': { bg: 'bg-gray-800', text: 'text-gray-400', label: 'Call End' },
  'call.status_changed': { bg: 'bg-blue-900/30', text: 'text-blue-400', label: 'Status' },
  'agent.status_changed': { bg: 'bg-vox-600/20', text: 'text-vox-300', label: 'Agent' },
  'escalation.created': { bg: 'bg-amber-900/30', text: 'text-amber-400', label: 'Escalation' },
  'escalation.assigned': { bg: 'bg-blue-900/30', text: 'text-blue-400', label: 'Assigned' },
  'escalation.resolved': { bg: 'bg-green-900/30', text: 'text-green-400', label: 'Resolved' },
  'alert.fired': { bg: 'bg-red-900/30', text: 'text-red-400', label: 'Alert' },
  'violation.detected': { bg: 'bg-red-900/30', text: 'text-red-400', label: 'Violation' },
  'metric.updated': { bg: 'bg-gray-800', text: 'text-gray-400', label: 'Metric' },
};

const AGENT_STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  available: { bg: 'bg-green-900/30', text: 'text-green-400' },
  busy: { bg: 'bg-red-900/30', text: 'text-red-400' },
  offline: { bg: 'bg-gray-800', text: 'text-gray-500' },
  break: { bg: 'bg-amber-900/30', text: 'text-amber-400' },
};

export default function LiveMonitor() {
  const { status: wsStatus, subscribeAll, unsubscribeAll } = useWS();
  const [loading, setLoading] = useState(true);
  const [snapshot, setSnapshot] = useState<LiveSnapshot | null>(null);
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [activeCalls, setActiveCalls] = useState<ActiveCallItem[]>([]);
  const [agents, setAgents] = useState<AgentPresenceItem[]>([]);
  const [paused, setPaused] = useState(false);
  const eventsEndRef = useRef<HTMLDivElement>(null);

  // Fetch initial data
  const fetchData = async () => {
    try {
      const [snap, calls, presence] = await Promise.all([
        liveApi.getDashboard(),
        liveApi.getActiveCalls(),
        liveApi.getAgentPresence(),
      ]);
      setSnapshot(snap);
      setActiveCalls(calls);
      setAgents(presence);
      if (snap.recent_events) {
        setEvents(snap.recent_events);
      }
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  // Periodic refresh as fallback (every 10s)
  useEffect(() => {
    const timer = setInterval(fetchData, 10000);
    return () => clearInterval(timer);
  }, []);

  // WebSocket event handler
  const handleEvent = useCallback((event: any) => {
    if (!paused) {
      setEvents(prev => [event, ...prev].slice(0, 50));
    }

    // Update snapshot counters based on event type
    if (event.type === 'call.started') {
      setSnapshot(prev => prev ? { ...prev, active_calls: prev.active_calls + 1, calls_today: prev.calls_today + 1 } : prev);
      setActiveCalls(prev => [...prev, {
        call_id: event.payload.call_id || '',
        agent_name: event.payload.agent_name || '',
        direction: event.payload.direction || 'inbound',
        from_number: event.payload.from_number || '',
        to_number: event.payload.to_number || '',
        started_at: event.timestamp,
        status: 'in_progress',
        duration_seconds: 0,
      }]);
    } else if (event.type === 'call.ended') {
      setSnapshot(prev => prev ? { ...prev, active_calls: Math.max(0, prev.active_calls - 1) } : prev);
      setActiveCalls(prev => prev.filter(c => c.call_id !== event.payload.call_id));
    } else if (event.type === 'agent.status_changed') {
      setAgents(prev => prev.map(a =>
        a.id === event.payload.agent_id
          ? { ...a, status: event.payload.new_status }
          : a
      ));
      // Refresh counts
      fetchData();
    } else if (event.type === 'escalation.created') {
      setSnapshot(prev => prev ? { ...prev, queue_depth: prev.queue_depth + 1 } : prev);
    } else if (event.type === 'escalation.resolved') {
      setSnapshot(prev => prev ? { ...prev, queue_depth: Math.max(0, prev.queue_depth - 1) } : prev);
    }
  }, [paused]);

  // Subscribe to all WebSocket events
  useEffect(() => {
    subscribeAll(handleEvent);
    return () => unsubscribeAll(handleEvent);
  }, [subscribeAll, unsubscribeAll, handleEvent]);

  // Auto-scroll events
  useEffect(() => {
    if (!paused) {
      eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events, paused]);

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
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            Live Monitor
            <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${
              wsStatus === 'connected' ? 'bg-green-900/30 text-green-400' :
              wsStatus === 'connecting' ? 'bg-amber-900/30 text-amber-400' :
              'bg-red-900/30 text-red-400'
            }`}>
              <span className={`w-2 h-2 rounded-full ${
                wsStatus === 'connected' ? 'bg-green-400 animate-pulse' :
                wsStatus === 'connecting' ? 'bg-amber-400' :
                'bg-red-400'
              }`} />
              {wsStatus === 'connected' ? 'Live' : wsStatus === 'connecting' ? 'Connecting...' : 'Offline'}
            </span>
          </h1>
          <p className="text-sm text-gray-400 mt-1">Real-time call monitoring, events, and agent presence</p>
        </div>
        <button
          onClick={fetchData}
          className="px-4 py-2 bg-[#1a1230] border border-vox-900/50 text-gray-400 hover:text-white rounded-lg text-sm transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* KPI Cards */}
      {snapshot && (
        <div className="grid grid-cols-6 gap-3 mb-6">
          {[
            { label: 'Active Calls', value: snapshot.active_calls, color: snapshot.active_calls > 0 ? 'text-green-400' : 'text-white', pulse: snapshot.active_calls > 0 },
            { label: 'Calls Today', value: snapshot.calls_today, color: 'text-white' },
            { label: 'AI Containment', value: `${(snapshot.containment_rate * 100).toFixed(1)}%`, color: snapshot.containment_rate > 0.7 ? 'text-green-400' : 'text-amber-400' },
            { label: 'Queue Depth', value: snapshot.queue_depth, color: snapshot.queue_depth > 5 ? 'text-red-400' : 'text-white' },
            { label: 'Active Agents', value: `${snapshot.active_agents}/${snapshot.total_agents}`, color: 'text-vox-400' },
            { label: 'Calls/min', value: snapshot.calls_per_minute, color: 'text-white' },
          ].map(kpi => (
            <div key={kpi.label} className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-3 text-center">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">{kpi.label}</p>
              <p className={`text-xl font-bold mt-0.5 ${kpi.color} ${(kpi as any).pulse ? 'animate-pulse' : ''}`}>{kpi.value}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* Event Feed */}
        <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Live Events</h3>
            <button
              onClick={() => setPaused(!paused)}
              className={`px-3 py-1 text-xs rounded-lg transition-colors ${
                paused ? 'bg-amber-900/30 text-amber-400' : 'bg-gray-800 text-gray-400 hover:text-white'
              }`}
            >
              {paused ? 'Paused' : 'Pause'}
            </button>
          </div>
          <div className="h-72 overflow-y-auto space-y-1.5" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}>
            {events.length === 0 ? (
              <p className="text-xs text-gray-600 text-center py-8">Waiting for events...</p>
            ) : (
              events.map((evt, i) => {
                const style = EVENT_COLORS[evt.type] || EVENT_COLORS['metric.updated'];
                const time = new Date(evt.timestamp).toLocaleTimeString();
                const description = getEventDescription(evt);
                return (
                  <div key={`${evt.timestamp}-${i}`} className="flex items-center gap-2 bg-[#0f0a1e] rounded-lg px-3 py-2">
                    <span className={`px-1.5 py-0.5 text-[9px] rounded font-medium ${style.bg} ${style.text}`}>{style.label}</span>
                    <span className="text-xs text-gray-300 flex-1 truncate">{description}</span>
                    <span className="text-[10px] text-gray-600 whitespace-nowrap">{time}</span>
                  </div>
                );
              })
            )}
            <div ref={eventsEndRef} />
          </div>
        </div>

        {/* Active Calls */}
        <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
            Active Calls ({activeCalls.length})
          </h3>
          {activeCalls.length === 0 ? (
            <p className="text-xs text-gray-600 text-center py-8">No active calls</p>
          ) : (
            <div className="h-72 overflow-y-auto space-y-2">
              {activeCalls.map(call => (
                <div key={call.call_id} className="bg-[#0f0a1e] rounded-lg p-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                      <span className="text-sm text-white font-medium">{call.agent_name || call.call_id}</span>
                    </div>
                    <span className="text-xs text-vox-400 uppercase">{call.direction}</span>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                    {call.from_number && <span>{call.from_number}</span>}
                    <span>{call.status}</span>
                    <span>{formatDuration(call.duration_seconds)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Agent Presence Grid */}
      <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
          Agent Presence ({agents.length})
        </h3>
        {agents.length === 0 ? (
          <p className="text-xs text-gray-600 text-center py-4">No human agents configured</p>
        ) : (
          <div className="grid grid-cols-4 gap-3">
            {agents.map(agent => {
              const style = AGENT_STATUS_COLORS[agent.status] || AGENT_STATUS_COLORS.offline;
              return (
                <div key={agent.id} className={`rounded-lg p-3 border border-vox-900/30 ${style.bg}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-white">{agent.name}</span>
                    <span className={`text-[10px] uppercase font-medium ${style.text}`}>{agent.status}</span>
                  </div>
                  <div className="text-xs text-gray-500">
                    {agent.calls_handled_today} calls today
                    {agent.current_call_id && <span className="text-vox-400 ml-2">On call</span>}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function getEventDescription(evt: LiveEvent): string {
  const p = evt.payload || {};
  switch (evt.type) {
    case 'call.started': return `Call started${p.agent_name ? ` via ${p.agent_name}` : ''} (${p.direction || 'inbound'})`;
    case 'call.ended': return `Call ended${p.call_id ? ` ${p.call_id.slice(0, 12)}` : ''}`;
    case 'call.status_changed': return `Call ${p.call_id?.slice(0, 12) || ''} → ${p.status || 'unknown'}`;
    case 'agent.status_changed': return `${p.agent_name || 'Agent'}: ${p.old_status} → ${p.new_status}`;
    case 'escalation.created': return `Escalation: ${p.reason || p.call_id || 'new'} (${p.priority || 'normal'})`;
    case 'escalation.assigned': return `Assigned to ${p.agent_name || 'agent'} (${p.wait_time_seconds?.toFixed(0) || 0}s wait)`;
    case 'escalation.resolved': return `Resolved (${p.handle_time_seconds?.toFixed(0) || 0}s handle)`;
    case 'alert.fired': return `${p.severity?.toUpperCase() || 'ALERT'}: ${p.title || p.message || 'Alert fired'}`;
    case 'violation.detected': return `Violation: ${p.description || p.rule_type || 'detected'}`;
    default: return evt.type;
  }
}

function formatDuration(seconds: number): string {
  if (!seconds || seconds < 0) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}
