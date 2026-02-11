import React, { useEffect, useState } from 'react';
import { keysApi } from '../services/api';
import { ApiKey } from '../types';

export default function ApiKeys() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKey, setNewKey] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchKeys = async () => {
    try {
      const data = await keysApi.list();
      setKeys(data);
    } catch (err) {
      console.error('Failed to fetch keys:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchKeys();
  }, []);

  const handleCreate = async () => {
    setCreating(true);
    try {
      const result = await keysApi.create(newKeyName || 'Default');
      setNewKey(result.key);
      setNewKeyName('');
      fetchKeys();
    } catch (err) {
      console.error('Failed to create key:', err);
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (keyId: string) => {
    if (!window.confirm('Are you sure you want to revoke this API key? This cannot be undone.')) return;
    try {
      await keysApi.revoke(keyId);
      fetchKeys();
    } catch (err) {
      console.error('Failed to revoke key:', err);
    }
  };

  const copyKey = () => {
    if (newKey) {
      navigator.clipboard.writeText(newKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

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
          <h1 className="text-2xl font-bold text-white">API Keys</h1>
          <p className="text-gray-400 mt-1">Manage your SDK authentication keys</p>
        </div>
        <button
          onClick={() => { setShowCreate(true); setNewKey(null); }}
          className="px-4 py-2 rounded-lg bg-vox-600 hover:bg-vox-500 text-white text-sm font-medium transition-colors"
        >
          Create Key
        </button>
      </div>

      {/* New key created banner */}
      {newKey && (
        <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
          <p className="text-sm text-emerald-400 font-medium mb-2">
            API key created! Copy it now - it won't be shown again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 px-3 py-2 rounded-lg bg-[#0f0a1e] text-white font-mono text-sm break-all">
              {newKey}
            </code>
            <button
              onClick={copyKey}
              className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition-colors whitespace-nowrap"
            >
              {copied ? 'Copied!' : 'Copy'}
            </button>
          </div>
          <div className="mt-3 p-3 rounded-lg bg-[#0f0a1e]">
            <p className="text-xs text-gray-400 mb-1">Use in your code:</p>
            <code className="text-xs text-vox-300 font-mono">
              bridge = VoxBridge({'{'}
              <br />
              &nbsp;&nbsp;"provider": "twilio",
              <br />
              &nbsp;&nbsp;"bot_url": "ws://localhost:9000/ws",
              <br />
              &nbsp;&nbsp;<span className="text-emerald-400">"api_key": "{newKey}"</span>,
              <br />
              {'}'})
            </code>
          </div>
        </div>
      )}

      {/* Create form */}
      {showCreate && !newKey && (
        <div className="mb-6 p-4 rounded-xl bg-[#1a1230] border border-vox-900/50">
          <h3 className="text-white font-medium mb-3">Create New API Key</h3>
          <div className="flex gap-3">
            <input
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="Key name (e.g., Production, Staging)"
              className="flex-1 px-4 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white placeholder-gray-500 focus:outline-none focus:border-vox-500 transition-colors text-sm"
            />
            <button
              onClick={handleCreate}
              disabled={creating}
              className="px-4 py-2 rounded-lg bg-vox-600 hover:bg-vox-500 text-white text-sm font-medium transition-colors disabled:opacity-50"
            >
              {creating ? 'Creating...' : 'Create'}
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white text-sm transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Keys list */}
      <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-vox-900/50">
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wide">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wide">Key</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wide">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wide">Last Used</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wide">Created</th>
              <th className="px-6 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-vox-900/30">
            {keys.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center text-gray-400">
                  No API keys yet. Create one to get started.
                </td>
              </tr>
            ) : (
              keys.map((key) => (
                <tr key={key.id} className="hover:bg-white/[0.02]">
                  <td className="px-6 py-4 text-sm text-white font-medium">{key.name}</td>
                  <td className="px-6 py-4">
                    <code className="text-sm text-gray-400 font-mono">{key.key_prefix}...</code>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex px-2 py-1 text-xs rounded-full font-medium ${
                      key.status === 'active'
                        ? 'bg-emerald-500/10 text-emerald-400'
                        : 'bg-red-500/10 text-red-400'
                    }`}>
                      {key.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400">
                    {key.last_used_at
                      ? new Date(key.last_used_at).toLocaleDateString()
                      : 'Never'}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400">
                    {new Date(key.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 text-right">
                    {key.status === 'active' && (
                      <button
                        onClick={() => handleRevoke(key.id)}
                        className="text-xs text-red-400 hover:text-red-300 transition-colors"
                      >
                        Revoke
                      </button>
                    )}
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
