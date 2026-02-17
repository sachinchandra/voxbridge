import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { agentsApi } from '../services/api';
import { AgentListItem, AgentStatus } from '../types';

const statusConfig: Record<AgentStatus, { label: string; color: string; dot: string }> = {
  draft: { label: 'Draft', color: 'bg-gray-600/20 text-gray-300', dot: 'bg-gray-400' },
  active: { label: 'Active', color: 'bg-emerald-600/20 text-emerald-300', dot: 'bg-emerald-400' },
  paused: { label: 'Paused', color: 'bg-amber-600/20 text-amber-300', dot: 'bg-amber-400' },
  archived: { label: 'Archived', color: 'bg-red-600/20 text-red-300', dot: 'bg-red-400' },
};

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Claude',
  deepgram: 'Deepgram',
  elevenlabs: 'ElevenLabs',
};

export default function Agents() {
  const [agents, setAgents] = useState<AgentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    agentsApi.list()
      .then(setAgents)
      .catch(() => setAgents([]))
      .finally(() => setLoading(false));
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
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">AI Agents</h1>
          <p className="text-gray-400 mt-1">Create and manage your AI voice agents</p>
        </div>
        <Link
          to="/dashboard/agents/new"
          className="px-4 py-2.5 rounded-lg bg-vox-600 hover:bg-vox-500 text-white text-sm font-medium transition-colors flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Create Agent
        </Link>
      </div>

      {agents.length === 0 ? (
        <div className="bg-[#1a1230] rounded-xl p-12 border border-vox-900/50 text-center">
          <div className="w-16 h-16 rounded-full bg-vox-600/20 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-vox-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
          </div>
          <h3 className="text-white font-medium text-lg mb-2">No agents yet</h3>
          <p className="text-gray-400 text-sm mb-6 max-w-md mx-auto">
            Create your first AI agent to start handling calls. Configure its personality, voice, and knowledge.
          </p>
          <Link
            to="/dashboard/agents/new"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-vox-600 hover:bg-vox-500 text-white text-sm font-medium transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Create Your First Agent
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((agent) => {
            const status = statusConfig[agent.status];
            return (
              <div
                key={agent.id}
                onClick={() => navigate(`/dashboard/agents/${agent.id}`)}
                className="bg-[#1a1230] rounded-xl p-5 border border-vox-900/50 hover:border-vox-600/50 transition-colors cursor-pointer group"
              >
                {/* Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-white font-medium truncate group-hover:text-vox-300 transition-colors">
                      {agent.name}
                    </h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-xs rounded-full ${status.color}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${status.dot}`}></span>
                        {status.label}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Provider badges */}
                <div className="flex items-center gap-2 mb-4">
                  <span className="px-2 py-1 text-xs rounded bg-[#0f0a1e] text-gray-300 border border-vox-900/30">
                    {providerLabels[agent.llm_provider] || agent.llm_provider}
                  </span>
                  <span className="px-2 py-1 text-xs rounded bg-[#0f0a1e] text-gray-300 border border-vox-900/30">
                    {agent.llm_model}
                  </span>
                  <span className="px-2 py-1 text-xs rounded bg-[#0f0a1e] text-gray-300 border border-vox-900/30">
                    {providerLabels[agent.tts_provider] || agent.tts_provider}
                  </span>
                </div>

                {/* Stats */}
                <div className="flex items-center gap-4 text-xs text-gray-400 pt-3 border-t border-vox-900/30">
                  <div className="flex items-center gap-1">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                    </svg>
                    {agent.total_calls} calls
                  </div>
                  <div className="flex items-center gap-1">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {agent.avg_duration > 0 ? `${agent.avg_duration.toFixed(0)}s avg` : 'No calls'}
                  </div>
                  <div className="flex-1 text-right text-gray-500">
                    {new Date(agent.created_at).toLocaleDateString()}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
