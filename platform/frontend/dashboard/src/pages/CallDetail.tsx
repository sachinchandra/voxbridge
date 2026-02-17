import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { callsApi } from '../services/api';
import { CallDetail as CallDetailType } from '../types';

export default function CallDetail() {
  const { callId } = useParams();
  const navigate = useNavigate();
  const [call, setCall] = useState<CallDetailType | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (callId) {
      callsApi.get(callId)
        .then(setCall)
        .catch(() => setCall(null))
        .finally(() => setLoading(false));
    }
  }, [callId]);

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-vox-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  if (!call) {
    return (
      <div className="text-center py-16">
        <p className="text-gray-400 mb-4">Call not found</p>
        <button onClick={() => navigate('/dashboard/calls')} className="text-vox-400 hover:text-vox-300 text-sm">
          Back to calls
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <button
          onClick={() => navigate('/dashboard/calls')}
          className="text-gray-400 hover:text-white transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div>
          <h1 className="text-2xl font-bold text-white">Call Detail</h1>
          <p className="text-gray-400 text-sm">{call.agent_name} &middot; {new Date(call.started_at).toLocaleString()}</p>
        </div>
      </div>

      {/* Call info cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <InfoCard label="Direction" value={call.direction} />
        <InfoCard label="Duration" value={formatDuration(call.duration_seconds)} />
        <InfoCard label="Status" value={call.status.replace('_', ' ')} />
        <InfoCard label="Cost" value={`$${(call.cost_cents / 100).toFixed(2)}`} />
        <InfoCard label="From" value={call.from_number || '—'} />
        <InfoCard label="To" value={call.to_number || '—'} />
        <InfoCard label="Escalated" value={call.escalated_to_human ? 'Yes' : 'No'} />
        <InfoCard
          label="Sentiment"
          value={call.sentiment_score != null ? `${(call.sentiment_score * 100).toFixed(0)}%` : '—'}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Transcript (takes 2 cols) */}
        <div className="lg:col-span-2">
          <div className="bg-[#1a1230] rounded-xl border border-vox-900/50">
            <div className="px-5 py-4 border-b border-vox-900/50">
              <h3 className="text-sm font-medium text-gray-300">Transcript</h3>
            </div>
            <div className="p-5 max-h-[600px] overflow-y-auto space-y-4">
              {call.transcript.length === 0 ? (
                <p className="text-gray-500 text-sm text-center py-8">No transcript available</p>
              ) : (
                call.transcript.map((msg, i) => (
                  <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                    {msg.role !== 'user' && (
                      <div className="w-7 h-7 rounded-full bg-vox-600 flex-shrink-0 flex items-center justify-center">
                        <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                        </svg>
                      </div>
                    )}
                    <div className={`max-w-[80%] px-4 py-2.5 rounded-xl text-sm ${
                      msg.role === 'user'
                        ? 'bg-vox-600/20 text-vox-200 rounded-br-sm'
                        : 'bg-[#0f0a1e] text-gray-300 rounded-bl-sm'
                    }`}>
                      {msg.content}
                      {msg.timestamp && (
                        <span className="block text-[10px] text-gray-500 mt-1">
                          {new Date(msg.timestamp).toLocaleTimeString()}
                        </span>
                      )}
                    </div>
                    {msg.role === 'user' && (
                      <div className="w-7 h-7 rounded-full bg-gray-600 flex-shrink-0 flex items-center justify-center">
                        <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Side panel */}
        <div className="space-y-6">
          {/* Recording */}
          {call.recording_url && (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
              <h3 className="text-sm font-medium text-gray-300 mb-3">Recording</h3>
              <audio controls className="w-full" src={call.recording_url}>
                Your browser does not support audio playback.
              </audio>
            </div>
          )}

          {/* Tool Calls */}
          {call.tool_calls.length > 0 && (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50">
              <div className="px-5 py-4 border-b border-vox-900/50">
                <h3 className="text-sm font-medium text-gray-300">Tool Calls ({call.tool_calls.length})</h3>
              </div>
              <div className="p-5 space-y-3">
                {call.tool_calls.map((tc) => (
                  <div key={tc.id} className="bg-[#0f0a1e] rounded-lg p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-vox-300 font-mono">{tc.function_name}</span>
                      <span className="text-xs text-gray-500">{tc.duration_ms}ms</span>
                    </div>
                    <div className="text-xs text-gray-400 font-mono">
                      <p className="mb-1">Args: {JSON.stringify(tc.arguments)}</p>
                      <p>Result: {JSON.stringify(tc.result).slice(0, 120)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Metadata */}
          {Object.keys(call.metadata).length > 0 && (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
              <h3 className="text-sm font-medium text-gray-300 mb-3">Metadata</h3>
              <div className="text-xs text-gray-400 font-mono bg-[#0f0a1e] rounded-lg p-3 overflow-auto max-h-40">
                <pre>{JSON.stringify(call.metadata, null, 2)}</pre>
              </div>
            </div>
          )}

          {/* Call Summary */}
          <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-5">
            <h3 className="text-sm font-medium text-gray-300 mb-3">Summary</h3>
            <div className="space-y-2 text-xs">
              <SummaryRow label="Call ID" value={call.id.slice(0, 8) + '...'} />
              <SummaryRow label="Agent" value={call.agent_name} />
              <SummaryRow label="End Reason" value={call.end_reason || '—'} />
              <SummaryRow label="Resolution" value={call.resolution || '—'} />
              <SummaryRow label="Started" value={new Date(call.started_at).toLocaleString()} />
              {call.ended_at && <SummaryRow label="Ended" value={new Date(call.ended_at).toLocaleString()} />}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[#1a1230] rounded-xl p-4 border border-vox-900/50">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-sm text-white mt-1 capitalize">{value}</p>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-300">{value}</span>
    </div>
  );
}
