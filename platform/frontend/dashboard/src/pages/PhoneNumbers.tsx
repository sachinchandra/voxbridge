import React, { useEffect, useState } from 'react';
import { phoneNumbersApi, agentsApi } from '../services/api';
import { PhoneNumber, PhoneNumberSearchResult, AgentListItem } from '../types';

const statusConfig: Record<string, { label: string; color: string; dot: string }> = {
  active: { label: 'Active', color: 'bg-emerald-600/20 text-emerald-300', dot: 'bg-emerald-400' },
  released: { label: 'Released', color: 'bg-red-600/20 text-red-300', dot: 'bg-red-400' },
  pending: { label: 'Pending', color: 'bg-amber-600/20 text-amber-300', dot: 'bg-amber-400' },
};

function formatPhone(phone: string): string {
  // Format E.164 to readable: +15551234567 → (555) 123-4567
  if (phone.startsWith('+1') && phone.length === 12) {
    return `(${phone.slice(2, 5)}) ${phone.slice(5, 8)}-${phone.slice(8)}`;
  }
  return phone;
}

export default function PhoneNumbers() {
  const [phones, setPhones] = useState<PhoneNumber[]>([]);
  const [agents, setAgents] = useState<AgentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showBuyModal, setShowBuyModal] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<PhoneNumberSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchAreaCode, setSearchAreaCode] = useState('');
  const [searchCountry, setSearchCountry] = useState('US');
  const [buyingNumber, setBuyingNumber] = useState('');
  const [selectedAgent, setSelectedAgent] = useState('');
  const [error, setError] = useState('');

  const loadData = async () => {
    try {
      const [phoneData, agentData] = await Promise.all([
        phoneNumbersApi.list(),
        agentsApi.list(),
      ]);
      setPhones(phoneData);
      setAgents(agentData);
    } catch {
      setPhones([]);
      setAgents([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSearch = async () => {
    setSearching(true);
    setError('');
    try {
      const results = await phoneNumbersApi.search({
        country: searchCountry,
        area_code: searchAreaCode || undefined,
        limit: 10,
      });
      setSearchResults(results);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to search numbers');
    } finally {
      setSearching(false);
    }
  };

  const handleBuy = async (phoneNumber: string) => {
    setBuyingNumber(phoneNumber);
    setError('');
    try {
      await phoneNumbersApi.buy(phoneNumber, selectedAgent || undefined);
      setShowBuyModal(false);
      setSearchResults([]);
      setSelectedAgent('');
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to buy number');
    } finally {
      setBuyingNumber('');
    }
  };

  const handleAssign = async (phoneId: string, agentId: string | null) => {
    try {
      await phoneNumbersApi.update(phoneId, agentId);
      setShowAssignModal(null);
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to assign number');
    }
  };

  const handleRelease = async (phoneId: string) => {
    if (!window.confirm('Are you sure you want to release this phone number? This action cannot be undone.')) {
      return;
    }
    try {
      await phoneNumbersApi.release(phoneId);
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to release number');
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
          <h1 className="text-2xl font-bold text-white">Phone Numbers</h1>
          <p className="text-gray-400 mt-1">Manage phone numbers for inbound and outbound calls</p>
        </div>
        <button
          onClick={() => setShowBuyModal(true)}
          className="px-4 py-2.5 rounded-lg bg-vox-600 hover:bg-vox-500 text-white text-sm font-medium transition-colors flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Buy Number
        </button>
      </div>

      {error && (
        <div className="mb-6 p-4 rounded-lg bg-red-600/10 border border-red-600/20 text-red-300 text-sm">
          {error}
          <button onClick={() => setError('')} className="float-right text-red-400 hover:text-red-300">&times;</button>
        </div>
      )}

      {phones.length === 0 ? (
        <div className="bg-[#1a1230] rounded-xl p-12 border border-vox-900/50 text-center">
          <div className="w-16 h-16 rounded-full bg-vox-600/20 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-vox-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
            </svg>
          </div>
          <h3 className="text-white font-medium text-lg mb-2">No phone numbers yet</h3>
          <p className="text-gray-400 text-sm mb-6 max-w-md mx-auto">
            Buy a phone number to start receiving inbound calls or making outbound calls through your AI agents.
          </p>
          <button
            onClick={() => setShowBuyModal(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-vox-600 hover:bg-vox-500 text-white text-sm font-medium transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Buy Your First Number
          </button>
        </div>
      ) : (
        <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-vox-900/50">
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Number</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Agent</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Provider</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Country</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-gray-400 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-vox-900/30">
              {phones.map((phone) => {
                const st = statusConfig[phone.status] || statusConfig.active;
                return (
                  <tr key={phone.id} className="hover:bg-white/5 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-lg bg-vox-600/20 flex items-center justify-center">
                          <svg className="w-4 h-4 text-vox-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                          </svg>
                        </div>
                        <div>
                          <p className="text-white font-medium text-sm">{formatPhone(phone.phone_number)}</p>
                          <p className="text-gray-500 text-xs font-mono">{phone.phone_number}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${st.color}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${st.dot}`}></span>
                        {st.label}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {phone.agent_name ? (
                        <span className="text-sm text-white">{phone.agent_name}</span>
                      ) : (
                        <button
                          onClick={() => setShowAssignModal(phone.id)}
                          className="text-sm text-vox-400 hover:text-vox-300 transition-colors"
                        >
                          + Assign agent
                        </button>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-400 capitalize">{phone.provider}</td>
                    <td className="px-6 py-4 text-sm text-gray-400">{phone.country}</td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => setShowAssignModal(phone.id)}
                          className="px-3 py-1.5 rounded-md text-xs text-gray-300 hover:text-white hover:bg-white/10 transition-colors"
                        >
                          Reassign
                        </button>
                        <button
                          onClick={() => handleRelease(phone.id)}
                          className="px-3 py-1.5 rounded-md text-xs text-red-400 hover:text-red-300 hover:bg-red-600/10 transition-colors"
                        >
                          Release
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Buy Number Modal */}
      {showBuyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#1a1230] rounded-2xl border border-vox-900/50 w-full max-w-lg mx-4 max-h-[80vh] overflow-auto">
            <div className="p-6 border-b border-vox-900/50">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-white">Buy a Phone Number</h2>
                <button
                  onClick={() => { setShowBuyModal(false); setSearchResults([]); setError(''); }}
                  className="text-gray-400 hover:text-white"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            <div className="p-6 space-y-4">
              {/* Search Controls */}
              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">Country</label>
                  <select
                    value={searchCountry}
                    onChange={(e) => setSearchCountry(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm focus:border-vox-500 focus:outline-none"
                  >
                    <option value="US">United States</option>
                    <option value="CA">Canada</option>
                    <option value="GB">United Kingdom</option>
                  </select>
                </div>
                <div className="flex-1">
                  <label className="block text-xs font-medium text-gray-400 mb-1.5">Area Code</label>
                  <input
                    type="text"
                    placeholder="e.g. 415"
                    value={searchAreaCode}
                    onChange={(e) => setSearchAreaCode(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:border-vox-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">Assign to Agent (optional)</label>
                <select
                  value={selectedAgent}
                  onChange={(e) => setSelectedAgent(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm focus:border-vox-500 focus:outline-none"
                >
                  <option value="">No agent (assign later)</option>
                  {agents.filter(a => a.status === 'active').map((agent) => (
                    <option key={agent.id} value={agent.id}>{agent.name}</option>
                  ))}
                </select>
              </div>

              <button
                onClick={handleSearch}
                disabled={searching}
                className="w-full px-4 py-2.5 rounded-lg bg-vox-600 hover:bg-vox-500 disabled:bg-vox-800 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
              >
                {searching ? 'Searching...' : 'Search Available Numbers'}
              </button>

              {/* Search Results */}
              {searchResults.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs text-gray-400 font-medium">{searchResults.length} numbers found</p>
                  {searchResults.map((result) => (
                    <div
                      key={result.phone_number}
                      className="flex items-center justify-between p-3 rounded-lg bg-[#0f0a1e] border border-vox-900/30 hover:border-vox-500/30 transition-colors"
                    >
                      <div>
                        <p className="text-white text-sm font-medium">{result.friendly_name || formatPhone(result.phone_number)}</p>
                        <p className="text-gray-500 text-xs">
                          {result.region && `${result.region} · `}
                          {result.capabilities.join(', ')} · ${(result.monthly_cost_cents / 100).toFixed(2)}/mo
                        </p>
                      </div>
                      <button
                        onClick={() => handleBuy(result.phone_number)}
                        disabled={buyingNumber === result.phone_number}
                        className="px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 text-white text-xs font-medium transition-colors"
                      >
                        {buyingNumber === result.phone_number ? 'Buying...' : 'Buy'}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Assign Agent Modal */}
      {showAssignModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#1a1230] rounded-2xl border border-vox-900/50 w-full max-w-sm mx-4">
            <div className="p-6 border-b border-vox-900/50">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-white">Assign Agent</h2>
                <button
                  onClick={() => setShowAssignModal(null)}
                  className="text-gray-400 hover:text-white"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            <div className="p-6 space-y-3">
              <p className="text-sm text-gray-400 mb-4">Select an agent to handle calls on this number:</p>
              <button
                onClick={() => handleAssign(showAssignModal, null)}
                className="w-full text-left px-4 py-3 rounded-lg border border-vox-900/30 hover:bg-white/5 text-gray-400 text-sm transition-colors"
              >
                Unassign (no agent)
              </button>
              {agents.filter(a => a.status === 'active').map((agent) => (
                <button
                  key={agent.id}
                  onClick={() => handleAssign(showAssignModal, agent.id)}
                  className="w-full text-left px-4 py-3 rounded-lg border border-vox-900/30 hover:bg-vox-600/10 hover:border-vox-500/30 text-white text-sm transition-colors flex items-center justify-between"
                >
                  <span>{agent.name}</span>
                  <span className="text-xs text-gray-500">{agent.llm_model}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
