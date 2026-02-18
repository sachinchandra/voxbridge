import axios from 'axios';
import {
  AuthResponse, ApiKey, UsageSummary, UsageRecord, Plan,
  Agent, AgentListItem, AgentStats, AgentCreatePayload,
  CallDetail, CallsListResponse, CallsOverview,
  PhoneNumber, PhoneNumberSearchResult, OutboundCallResponse,
} from '../types';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to all requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('voxbridge_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 errors
api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('voxbridge_token');
      localStorage.removeItem('voxbridge_customer');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ── Auth ──────────────────────────────────────────────────────────

export const authApi = {
  signup: async (email: string, password: string, name: string): Promise<AuthResponse> => {
    const { data } = await api.post('/auth/signup', { email, password, name });
    return data;
  },

  login: async (email: string, password: string): Promise<AuthResponse> => {
    const { data } = await api.post('/auth/login', { email, password });
    return data;
  },

  getProfile: async () => {
    const { data } = await api.get('/auth/me');
    return data;
  },
};

// ── API Keys ─────────────────────────────────────────────────────

export const keysApi = {
  list: async (): Promise<ApiKey[]> => {
    const { data } = await api.get('/api-keys');
    return data;
  },

  create: async (name: string): Promise<ApiKey & { key: string }> => {
    const { data } = await api.post('/api-keys', { name });
    return data;
  },

  revoke: async (keyId: string): Promise<void> => {
    await api.delete(`/api-keys/${keyId}`);
  },
};

// ── Usage ────────────────────────────────────────────────────────

export const usageApi = {
  getSummary: async (): Promise<UsageSummary> => {
    const { data } = await api.get('/usage/summary');
    return data;
  },

  getHistory: async (limit = 50): Promise<UsageRecord[]> => {
    const { data } = await api.get(`/usage/history?limit=${limit}`);
    return data;
  },
};

// ── Billing ──────────────────────────────────────────────────────

export const billingApi = {
  getPlans: async (): Promise<{ plans: Plan[] }> => {
    const { data } = await api.get('/billing/plans');
    return data;
  },

  getCurrentPlan: async () => {
    const { data } = await api.get('/billing/current');
    return data;
  },

  createCheckout: async (plan: string): Promise<{ checkout_url: string }> => {
    const { data } = await api.post('/billing/checkout', { plan });
    return data;
  },

  createPortalSession: async (): Promise<{ portal_url: string }> => {
    const { data } = await api.post('/billing/portal');
    return data;
  },
};

// ── Agents ──────────────────────────────────────────────────────

export const agentsApi = {
  list: async (): Promise<AgentListItem[]> => {
    const { data } = await api.get('/agents');
    return data;
  },

  get: async (agentId: string): Promise<Agent> => {
    const { data } = await api.get(`/agents/${agentId}`);
    return data;
  },

  create: async (payload: AgentCreatePayload): Promise<Agent> => {
    const { data } = await api.post('/agents', payload);
    return data;
  },

  update: async (agentId: string, payload: Partial<Agent>): Promise<Agent> => {
    const { data } = await api.patch(`/agents/${agentId}`, payload);
    return data;
  },

  delete: async (agentId: string): Promise<void> => {
    await api.delete(`/agents/${agentId}`);
  },

  getStats: async (agentId: string): Promise<AgentStats> => {
    const { data } = await api.get(`/agents/${agentId}/stats`);
    return data;
  },
};

// ── Calls ───────────────────────────────────────────────────────

export const callsApi = {
  list: async (params?: {
    agent_id?: string;
    status?: string;
    direction?: string;
    limit?: number;
    offset?: number;
  }): Promise<CallsListResponse> => {
    const { data } = await api.get('/calls', { params });
    return data;
  },

  get: async (callId: string): Promise<CallDetail> => {
    const { data } = await api.get(`/calls/${callId}`);
    return data;
  },

  getOverview: async (): Promise<CallsOverview> => {
    const { data } = await api.get('/calls/summary/overview');
    return data;
  },

  initiateOutbound: async (payload: {
    agent_id: string;
    to: string;
    from_number_id?: string;
    metadata?: Record<string, any>;
  }): Promise<OutboundCallResponse> => {
    const { data } = await api.post('/calls', payload);
    return data;
  },
};

// ── Phone Numbers ────────────────────────────────────────────────

export const phoneNumbersApi = {
  list: async (): Promise<PhoneNumber[]> => {
    const { data } = await api.get('/phone-numbers');
    return data;
  },

  get: async (phoneId: string): Promise<PhoneNumber> => {
    const { data } = await api.get(`/phone-numbers/${phoneId}`);
    return data;
  },

  search: async (params?: {
    country?: string;
    area_code?: string;
    contains?: string;
    limit?: number;
  }): Promise<PhoneNumberSearchResult[]> => {
    const { data } = await api.post('/phone-numbers/search', params || {});
    return data;
  },

  buy: async (phone_number: string, agent_id?: string): Promise<PhoneNumber> => {
    const { data } = await api.post('/phone-numbers/buy', { phone_number, agent_id });
    return data;
  },

  update: async (phoneId: string, agent_id: string | null): Promise<PhoneNumber> => {
    const { data } = await api.patch(`/phone-numbers/${phoneId}`, { agent_id });
    return data;
  },

  release: async (phoneId: string): Promise<void> => {
    await api.delete(`/phone-numbers/${phoneId}`);
  },
};

export default api;
