export interface Customer {
  id: string;
  email: string;
  name: string;
  plan: 'free' | 'pro' | 'enterprise';
  created_at: string;
}

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  key?: string; // only present on creation
  status: 'active' | 'revoked' | 'expired';
  last_used_at: string | null;
  created_at: string;
}

export interface UsageSummary {
  total_minutes: number;
  total_calls: number;
  plan_minutes_limit: number;
  minutes_remaining: number;
  period_start: string;
  period_end: string;
  daily_usage: Array<{ date: string; minutes: number }>;
  provider_breakdown: Array<{ provider: string; calls: number }>;
}

export interface UsageRecord {
  id: string;
  session_id: string;
  call_id: string;
  provider: string;
  duration_seconds: number;
  status: string;
  created_at: string;
}

export interface Plan {
  id: string;
  name: string;
  price: number;
  minutes: number;
  max_concurrent: number;
  features: string[];
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  customer: Customer;
}

// ── Agents ──────────────────────────────────────────────────────

export type AgentStatus = 'draft' | 'active' | 'paused' | 'archived';

export interface Agent {
  id: string;
  name: string;
  status: AgentStatus;
  system_prompt: string;
  first_message: string;
  end_call_phrases: string[];
  stt_provider: string;
  stt_config: Record<string, any>;
  llm_provider: string;
  llm_model: string;
  llm_config: Record<string, any>;
  tts_provider: string;
  tts_voice_id: string;
  tts_config: Record<string, any>;
  max_duration_seconds: number;
  interruption_enabled: boolean;
  tools: any[];
  knowledge_base_id: string | null;
  escalation_config: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface AgentListItem {
  id: string;
  name: string;
  status: AgentStatus;
  llm_provider: string;
  llm_model: string;
  tts_provider: string;
  total_calls: number;
  avg_duration: number;
  created_at: string;
}

export interface AgentStats {
  agent_id: string;
  agent_name: string;
  total_calls: number;
  completed_calls: number;
  failed_calls: number;
  escalated_calls: number;
  avg_duration_seconds: number;
  total_duration_minutes: number;
  avg_sentiment: number | null;
  resolution_rate: number;
  containment_rate: number;
  total_cost_cents: number;
  calls_by_day: Array<{ date: string; calls: number }>;
}

export interface AgentCreatePayload {
  name: string;
  system_prompt?: string;
  first_message?: string;
  end_call_phrases?: string[];
  stt_provider?: string;
  llm_provider?: string;
  llm_model?: string;
  tts_provider?: string;
  tts_voice_id?: string;
  max_duration_seconds?: number;
  interruption_enabled?: boolean;
  escalation_config?: Record<string, any>;
}

// ── Calls ───────────────────────────────────────────────────────

export type CallDirection = 'inbound' | 'outbound';
export type CallStatusType = 'initiated' | 'ringing' | 'in_progress' | 'completed' | 'failed' | 'no_answer' | 'busy';

export interface CallRecord {
  id: string;
  agent_id: string;
  agent_name: string;
  direction: CallDirection;
  from_number: string;
  to_number: string;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number;
  status: CallStatusType;
  end_reason: string;
  escalated_to_human: boolean;
  sentiment_score: number | null;
  resolution: string;
  cost_cents: number;
  created_at: string;
}

export interface CallDetail extends CallRecord {
  transcript: Array<{ role: string; content: string; timestamp?: string }>;
  recording_url: string;
  metadata: Record<string, any>;
  tool_calls: Array<{
    id: string;
    function_name: string;
    arguments: Record<string, any>;
    result: Record<string, any>;
    duration_ms: number;
    created_at: string;
  }>;
}

export interface CallsOverview {
  total_calls: number;
  ai_handled: number;
  escalated: number;
  containment_rate: number;
  avg_duration_seconds: number;
  total_cost_cents: number;
  total_cost_dollars: number;
}

export interface CallsListResponse {
  calls: CallRecord[];
  total: number;
  limit: number;
  offset: number;
}

// ── Phone Numbers ────────────────────────────────────────────────

export type PhoneNumberStatus = 'active' | 'released' | 'pending';

export interface PhoneNumber {
  id: string;
  phone_number: string;
  provider: string;
  country: string;
  capabilities: string[];
  status: PhoneNumberStatus;
  agent_id: string | null;
  agent_name: string;
  created_at: string;
}

export interface PhoneNumberSearchResult {
  phone_number: string;
  friendly_name: string;
  country: string;
  region: string;
  capabilities: string[];
  monthly_cost_cents: number;
}

export interface OutboundCallResponse {
  call_id: string;
  status: CallStatusType;
  from_number: string;
  to_number: string;
  agent_id: string;
  agent_name: string;
}

// ── Knowledge Base ───────────────────────────────────────────────

export type DocumentStatus = 'processing' | 'ready' | 'failed';

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  embedding_model: string;
  chunk_size: number;
  chunk_overlap: number;
  document_count: number;
  total_chunks: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface KBDocument {
  id: string;
  knowledge_base_id: string;
  filename: string;
  content_type: string;
  source_url: string;
  file_size_bytes: number;
  chunk_count: number;
  status: DocumentStatus;
  error_message: string;
  created_at: string;
}

// ── Agent Tools ──────────────────────────────────────────────────

export interface AgentTool {
  name: string;
  description: string;
  parameters: Record<string, any>;
  endpoint: string;
  method: string;
  headers?: Record<string, string>;
}

// ── QA Scores ───────────────────────────────────────────────────

export interface QAScore {
  id: string;
  call_id: string;
  agent_id: string;
  accuracy_score: number;
  tone_score: number;
  resolution_score: number;
  compliance_score: number;
  overall_score: number;
  pii_detected: boolean;
  angry_caller: boolean;
  flagged: boolean;
  flag_reasons: string[];
  summary: string;
  improvement_suggestions: string[];
  created_at: string;
}

export interface QASummary {
  total_scored: number;
  avg_overall: number;
  avg_accuracy: number;
  avg_tone: number;
  avg_resolution: number;
  avg_compliance: number;
  flagged_count: number;
  pii_count: number;
  angry_count: number;
  score_distribution: Array<{ range: string; count: number }>;
  top_flag_reasons: Array<{ reason: string; count: number }>;
}

// ── Playground ─────────────────────────────────────────────────

export interface PlaygroundMessage {
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  timestamp: number;
  latency_ms: number;
  tool_call?: {
    name: string;
    arguments: string;
    result?: any;
    duration_ms?: number;
  } | null;
}

export interface PlaygroundStartResponse {
  session_id: string;
  agent_name: string;
  first_message: string;
  llm_provider: string;
  llm_model: string;
}

export interface PlaygroundResponse {
  session_id: string;
  reply: string;
  tool_calls: Array<{ name: string; arguments: string }>;
  done: boolean;
  latency_ms: number;
  tokens_used: number;
}

export interface PlaygroundSessionDetail {
  session_id: string;
  agent_id: string;
  agent_name: string;
  status: 'active' | 'completed' | 'error';
  messages: PlaygroundMessage[];
  total_turns: number;
  total_tokens: number;
  estimated_cost_cents: number;
  started_at: string;
  ended_at: string | null;
}

// ── QA Report ──────────────────────────────────────────────────

export interface QAReportPreview {
  sent: boolean;
  report: {
    period: string;
    total_scored: number;
    avg_score: number;
    flagged: number;
    trend: string;
  };
}

// ── Conversation Flows ──────────────────────────────────────────

export type FlowNodeType = 'start' | 'message' | 'listen' | 'ai_respond' | 'condition' | 'tool_call' | 'transfer' | 'end';

export interface FlowNode {
  id: string;
  type: FlowNodeType;
  label: string;
  x: number;
  y: number;
  config: Record<string, any>;
}

export interface FlowEdge {
  id: string;
  source_id: string;
  target_id: string;
  label: string;
  condition: string;
}

export interface ConversationFlow {
  id: string;
  agent_id: string;
  name: string;
  description: string;
  nodes: FlowNode[];
  edges: FlowEdge[];
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface FlowListItem {
  id: string;
  agent_id: string;
  name: string;
  description: string;
  is_active: boolean;
  version: number;
  node_count: number;
  edge_count: number;
  created_at: string;
}

export interface FlowTestResult {
  flow_id: string;
  version: number;
  path: string[];
  messages: Array<{ role: string; content: string }>;
  completed: boolean;
  end_reason: string;
  duration_ms: number;
}

// ── Alerts ─────────────────────────────────────────────────────

export type AlertSeverity = 'info' | 'warning' | 'critical';
export type AlertTypeEnum = 'high_volume' | 'angry_caller_spike' | 'low_quality_score' | 'high_escalation_rate' | 'pii_detected' | 'agent_down' | 'api_failure' | 'cost_threshold';

export interface AlertRule {
  id: string;
  name: string;
  alert_type: AlertTypeEnum;
  severity: AlertSeverity;
  enabled: boolean;
  config: Record<string, any>;
  notify_email: boolean;
  notify_webhook: string;
  created_at: string;
}

export interface AlertItem {
  id: string;
  rule_id: string;
  alert_type: AlertTypeEnum;
  severity: AlertSeverity;
  title: string;
  message: string;
  metadata: Record<string, any>;
  acknowledged: boolean;
  acknowledged_at: string | null;
  created_at: string;
}

export interface AlertSummaryData {
  total: number;
  unacknowledged: number;
  critical: number;
  warning: number;
  info: number;
  recent: AlertItem[];
}

// -- Departments & Routing ---------------------------------------------------

export interface Department {
  id: string;
  customer_id: string;
  name: string;
  description: string;
  agent_id: string;
  transfer_number: string;
  priority: number;
  is_default: boolean;
  enabled: boolean;
  intent_keywords: string[];
  created_at: string;
}

export interface RoutingRule {
  id: string;
  customer_id: string;
  name: string;
  department_id: string;
  match_type: 'keyword' | 'regex' | 'dtmf' | 'intent_model';
  match_value: string;
  priority: number;
  enabled: boolean;
  created_at: string;
}

export interface RoutingResult {
  department_id: string;
  department_name: string;
  agent_id: string;
  transfer_number: string;
  confidence: number;
  matched_rule: string;
  matched_keywords: string[];
  fallback: boolean;
}

export interface RoutingConfigSummary {
  departments: number;
  rules: number;
  default_department: string | null;
  department_list: Array<{
    id: string;
    name: string;
    priority: number;
    enabled: boolean;
    is_default: boolean;
  }>;
}

// -- Connectors --------------------------------------------------------------

export type ConnectorType = 'genesys' | 'amazon_connect' | 'avaya' | 'cisco' | 'twilio' | 'five9' | 'generic_sip';
export type ConnectorStatusType = 'active' | 'inactive' | 'error' | 'configuring';

export interface ConnectorItem {
  id: string;
  customer_id: string;
  name: string;
  connector_type: ConnectorType;
  status: ConnectorStatusType;
  config: Record<string, any>;
  department_mappings: Record<string, string>;
  total_calls_routed: number;
  last_active_at: string | null;
  error_message: string;
  created_at: string;
  updated_at: string;
}

export interface ConnectorEvent {
  id: string;
  connector_id: string;
  event_type: string;
  message: string;
  metadata: Record<string, any>;
  created_at: string;
}

export interface ConnectorHealth {
  healthy: boolean;
  status: ConnectorStatusType;
  name: string;
  type: ConnectorType;
  total_calls_routed: number;
  last_active_at: string | null;
  error: string;
}

export interface AnalyticsDetail {
  total_calls: number;
  ai_handled: number;
  escalated: number;
  containment_rate: number;
  avg_duration_seconds: number;
  total_cost_cents: number;
  total_cost_dollars: number;
  sentiment_positive: number;
  sentiment_neutral: number;
  sentiment_negative: number;
  calls_by_hour: Array<{ hour: number; calls: number }>;
  escalation_reasons: Array<{ reason: string; count: number }>;
  resolved: number;
  abandoned: number;
  calls_by_day: Array<{ date: string; calls: number }>;
  agent_rankings: Array<{
    agent_id: string;
    agent_name: string;
    calls: number;
    containment_rate: number;
    avg_duration: number;
  }>;
}
