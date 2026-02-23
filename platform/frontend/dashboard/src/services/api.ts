import axios from 'axios';
import {
  AuthResponse, ApiKey, UsageSummary, UsageRecord, Plan,
  Agent, AgentListItem, AgentStats, AgentCreatePayload,
  CallDetail, CallsListResponse, CallsOverview,
  PhoneNumber, PhoneNumberSearchResult, OutboundCallResponse,
  KnowledgeBase, KBDocument,
  QAScore, QASummary, AnalyticsDetail,
  PlaygroundStartResponse, PlaygroundResponse, PlaygroundSessionDetail,
  QAReportPreview,
  ConversationFlow, FlowListItem, FlowTestResult,
  AlertRule, AlertItem, AlertSummaryData,
  Department, RoutingRule, RoutingResult, RoutingConfigSummary,
  ConnectorItem, ConnectorEvent, ConnectorHealth,
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

// ── Knowledge Bases ──────────────────────────────────────────────

export const knowledgeBasesApi = {
  list: async (): Promise<KnowledgeBase[]> => {
    const { data } = await api.get('/knowledge-bases');
    return data;
  },

  get: async (kbId: string): Promise<KnowledgeBase> => {
    const { data } = await api.get(`/knowledge-bases/${kbId}`);
    return data;
  },

  create: async (payload: { name: string; description?: string }): Promise<KnowledgeBase> => {
    const { data } = await api.post('/knowledge-bases', payload);
    return data;
  },

  update: async (kbId: string, payload: Partial<KnowledgeBase>): Promise<KnowledgeBase> => {
    const { data } = await api.patch(`/knowledge-bases/${kbId}`, payload);
    return data;
  },

  delete: async (kbId: string): Promise<void> => {
    await api.delete(`/knowledge-bases/${kbId}`);
  },

  listDocuments: async (kbId: string): Promise<KBDocument[]> => {
    const { data } = await api.get(`/knowledge-bases/${kbId}/documents`);
    return data;
  },

  uploadDocument: async (kbId: string, file: File): Promise<{ id: string; filename: string; status: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await api.post(`/knowledge-bases/${kbId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  deleteDocument: async (kbId: string, docId: string): Promise<void> => {
    await api.delete(`/knowledge-bases/${kbId}/documents/${docId}`);
  },
};

// ── Quality Assurance ────────────────────────────────────────────

export const qaApi = {
  scoreCall: async (callId: string): Promise<QAScore> => {
    const { data } = await api.post(`/qa/score/${callId}`);
    return data;
  },

  scoreBatch: async (limit?: number): Promise<{ scored: number; flagged: number; message: string }> => {
    const { data } = await api.post('/qa/score-batch', null, { params: { limit } });
    return data;
  },

  getCallScore: async (callId: string): Promise<QAScore> => {
    const { data } = await api.get(`/qa/calls/${callId}`);
    return data;
  },

  listScores: async (params?: {
    agent_id?: string;
    flagged?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<{ scores: QAScore[]; total: number }> => {
    const { data } = await api.get('/qa/scores', { params });
    return data;
  },

  getSummary: async (agentId?: string): Promise<QASummary> => {
    const { data } = await api.get('/qa/summary', { params: { agent_id: agentId } });
    return data;
  },

  getAnalytics: async (): Promise<AnalyticsDetail> => {
    const { data } = await api.get('/qa/analytics');
    return data;
  },
};

// ── Playground ──────────────────────────────────────────────────

export const playgroundApi = {
  start: async (agentId: string): Promise<PlaygroundStartResponse> => {
    const { data } = await api.post('/playground/start', { agent_id: agentId });
    return data;
  },

  sendMessage: async (sessionId: string, message: string): Promise<PlaygroundResponse> => {
    const { data } = await api.post('/playground/message', { session_id: sessionId, message });
    return data;
  },

  endSession: async (sessionId: string): Promise<{ session_id: string; status: string }> => {
    const { data } = await api.post(`/playground/end/${sessionId}`);
    return data;
  },

  getSession: async (sessionId: string): Promise<PlaygroundSessionDetail> => {
    const { data } = await api.get(`/playground/session/${sessionId}`);
    return data;
  },

  quickTest: async (agentId: string, message: string): Promise<PlaygroundResponse> => {
    const { data } = await api.post('/playground/quick-test', { agent_id: agentId, message });
    return data;
  },
};

// ── QA Reports ──────────────────────────────────────────────────

export const qaReportsApi = {
  send: async (): Promise<QAReportPreview> => {
    const { data } = await api.post('/qa-reports/send');
    return data;
  },

  previewUrl: `${API_URL}/api/v1/qa-reports/preview`,
};

// ── Conversation Flows ──────────────────────────────────────────

export const flowsApi = {
  list: async (): Promise<FlowListItem[]> => {
    const { data } = await api.get('/flows');
    return data;
  },

  get: async (flowId: string): Promise<ConversationFlow> => {
    const { data } = await api.get(`/flows/${flowId}`);
    return data;
  },

  create: async (payload: { agent_id?: string; name: string; description?: string }): Promise<ConversationFlow> => {
    const { data } = await api.post('/flows', payload);
    return data;
  },

  update: async (flowId: string, payload: Partial<ConversationFlow>): Promise<ConversationFlow> => {
    const { data } = await api.patch(`/flows/${flowId}`, payload);
    return data;
  },

  delete: async (flowId: string): Promise<void> => {
    await api.delete(`/flows/${flowId}`);
  },

  activate: async (flowId: string): Promise<{ activated: boolean }> => {
    const { data } = await api.post(`/flows/${flowId}/activate`);
    return data;
  },

  test: async (flowId: string, inputs: string[]): Promise<FlowTestResult> => {
    const { data } = await api.post(`/flows/${flowId}/test`, { inputs });
    return data;
  },

  createDefault: async (agentId: string, name?: string): Promise<ConversationFlow> => {
    const { data } = await api.post('/flows/default', { agent_id: agentId, name });
    return data;
  },
};

// ── Alerts ──────────────────────────────────────────────────────

export const alertsApi = {
  listRules: async (): Promise<AlertRule[]> => {
    const { data } = await api.get('/alerts/rules');
    return data;
  },

  createRule: async (payload: Partial<AlertRule>): Promise<AlertRule> => {
    const { data } = await api.post('/alerts/rules', payload);
    return data;
  },

  updateRule: async (ruleId: string, payload: Partial<AlertRule>): Promise<AlertRule> => {
    const { data } = await api.patch(`/alerts/rules/${ruleId}`, payload);
    return data;
  },

  deleteRule: async (ruleId: string): Promise<void> => {
    await api.delete(`/alerts/rules/${ruleId}`);
  },

  createDefaults: async (): Promise<{ created: number }> => {
    const { data } = await api.post('/alerts/rules/defaults');
    return data;
  },

  list: async (params?: { unacknowledged?: boolean; severity?: string; limit?: number }): Promise<AlertItem[]> => {
    const { data } = await api.get('/alerts', { params });
    return data;
  },

  getSummary: async (): Promise<AlertSummaryData> => {
    const { data } = await api.get('/alerts/summary');
    return data;
  },

  acknowledge: async (alertId: string): Promise<void> => {
    await api.post(`/alerts/${alertId}/acknowledge`);
  },

  acknowledgeAll: async (): Promise<{ acknowledged: number }> => {
    const { data } = await api.post('/alerts/acknowledge-all');
    return data;
  },
};

// -- Routing & Departments ---------------------------------------------------

export const routingApi = {
  listDepartments: async (): Promise<Department[]> => {
    const { data } = await api.get('/routing/departments');
    return data;
  },

  getDepartment: async (deptId: string): Promise<Department> => {
    const { data } = await api.get(`/routing/departments/${deptId}`);
    return data;
  },

  createDepartment: async (payload: {
    name: string;
    description?: string;
    agent_id?: string;
    transfer_number?: string;
    priority?: number;
    is_default?: boolean;
    intent_keywords?: string[];
  }): Promise<Department> => {
    const { data } = await api.post('/routing/departments', payload);
    return data;
  },

  updateDepartment: async (deptId: string, payload: Partial<Department>): Promise<Department> => {
    const { data } = await api.patch(`/routing/departments/${deptId}`, payload);
    return data;
  },

  deleteDepartment: async (deptId: string): Promise<void> => {
    await api.delete(`/routing/departments/${deptId}`);
  },

  createDefaults: async (): Promise<{ created: number; departments: Department[] }> => {
    const { data } = await api.post('/routing/departments/defaults');
    return data;
  },

  listRules: async (): Promise<RoutingRule[]> => {
    const { data } = await api.get('/routing/rules');
    return data;
  },

  createRule: async (payload: {
    name: string;
    department_id: string;
    match_type?: string;
    match_value?: string;
    priority?: number;
  }): Promise<RoutingRule> => {
    const { data } = await api.post('/routing/rules', payload);
    return data;
  },

  deleteRule: async (ruleId: string): Promise<void> => {
    await api.delete(`/routing/rules/${ruleId}`);
  },

  classify: async (text: string, dtmf_input?: string): Promise<RoutingResult> => {
    const { data } = await api.post('/routing/classify', { text, dtmf_input });
    return data;
  },

  getConfig: async (): Promise<RoutingConfigSummary> => {
    const { data } = await api.get('/routing/config');
    return data;
  },
};

// -- Connectors --------------------------------------------------------------

export const connectorsApi = {
  list: async (): Promise<ConnectorItem[]> => {
    const { data } = await api.get('/connectors');
    return data;
  },

  get: async (connId: string): Promise<ConnectorItem> => {
    const { data } = await api.get(`/connectors/${connId}`);
    return data;
  },

  create: async (payload: {
    name: string;
    connector_type: string;
    config?: Record<string, any>;
  }): Promise<ConnectorItem> => {
    const { data } = await api.post('/connectors', payload);
    return data;
  },

  update: async (connId: string, payload: { name?: string; config?: Record<string, any> }): Promise<ConnectorItem> => {
    const { data } = await api.patch(`/connectors/${connId}`, payload);
    return data;
  },

  delete: async (connId: string): Promise<void> => {
    await api.delete(`/connectors/${connId}`);
  },

  activate: async (connId: string): Promise<ConnectorItem> => {
    const { data } = await api.post(`/connectors/${connId}/activate`);
    return data;
  },

  deactivate: async (connId: string): Promise<ConnectorItem> => {
    const { data } = await api.post(`/connectors/${connId}/deactivate`);
    return data;
  },

  getHealth: async (connId: string): Promise<ConnectorHealth> => {
    const { data } = await api.get(`/connectors/${connId}/health`);
    return data;
  },

  getEvents: async (connId: string, limit?: number): Promise<ConnectorEvent[]> => {
    const { data } = await api.get(`/connectors/${connId}/events`, { params: { limit } });
    return data;
  },

  mapQueue: async (connId: string, external_queue_id: string, department_id: string): Promise<void> => {
    await api.post(`/connectors/${connId}/map-queue`, { external_queue_id, department_id });
  },
};

export default api;
