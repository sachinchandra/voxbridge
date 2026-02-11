import axios from 'axios';
import { AuthResponse, ApiKey, UsageSummary, UsageRecord, Plan } from '../types';

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

export default api;
