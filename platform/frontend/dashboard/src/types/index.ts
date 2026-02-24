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

// -- Agent Assist ------------------------------------------------------------

export type SuggestionType = 'response' | 'knowledge' | 'compliance' | 'action' | 'sentiment';

export interface AssistSuggestion {
  id: string;
  session_id: string;
  type: SuggestionType;
  content: string;
  confidence: number;
  source: string;
  accepted: boolean | null;
  created_at: string;
}

export interface AssistSessionItem {
  id: string;
  call_id: string;
  human_agent_name: string;
  status: 'active' | 'completed' | 'paused';
  suggestions_count: number;
  suggestions_accepted: number;
  compliance_warnings: number;
  caller_sentiment: string;
  created_at: string;
}

export interface AssistSessionDetail {
  id: string;
  customer_id: string;
  call_id: string;
  agent_id: string;
  human_agent_name: string;
  status: string;
  transcript: Array<{ role: string; content: string; timestamp: string }>;
  suggestions: AssistSuggestion[];
  suggestions_accepted: number;
  suggestions_dismissed: number;
  compliance_warnings: number;
  pii_detected: boolean;
  call_summary: string;
  next_steps: string[];
  caller_sentiment: string;
  created_at: string;
  ended_at: string | null;
}

export interface AssistSummaryData {
  total_sessions: number;
  active_sessions: number;
  total_suggestions: number;
  acceptance_rate: number;
  compliance_warnings: number;
  avg_suggestions_per_session: number;
}

// -- Compliance & Audit ------------------------------------------------------

export type ComplianceRuleType = 'pii_redaction' | 'script_adherence' | 'disclosure_required' | 'forbidden_phrases' | 'data_retention' | 'hipaa' | 'pci_dss';

export interface ComplianceRuleItem {
  id: string;
  customer_id: string;
  name: string;
  rule_type: ComplianceRuleType;
  enabled: boolean;
  config: Record<string, any>;
  severity: string;
  created_at: string;
}

export interface ComplianceViolationItem {
  id: string;
  customer_id: string;
  call_id: string;
  rule_id: string;
  rule_name: string;
  rule_type: ComplianceRuleType;
  severity: string;
  description: string;
  transcript_excerpt: string;
  redacted_text: string;
  resolved: boolean;
  resolved_by: string;
  created_at: string;
}

export interface ComplianceSummaryData {
  total_rules: number;
  enabled_rules: number;
  total_violations: number;
  unresolved_violations: number;
  violations_by_type: Record<string, number>;
  violations_by_severity: Record<string, number>;
  recent_violations: ComplianceViolationItem[];
  audit_log_count: number;
}

export interface AuditLogEntryItem {
  id: string;
  customer_id: string;
  user_email: string;
  action: string;
  resource_type: string;
  resource_id: string;
  description: string;
  metadata: Record<string, any>;
  ip_address: string;
  created_at: string;
}

// -- Workforce Management ----------------------------------------------------

export type HumanAgentStatusType = 'available' | 'busy' | 'offline' | 'break';
export type EscalationPriorityType = 'low' | 'normal' | 'high' | 'urgent';
export type EscalationStatusType = 'waiting' | 'assigned' | 'resolved' | 'abandoned';

export interface HumanAgentItem {
  id: string;
  customer_id: string;
  name: string;
  email: string;
  status: HumanAgentStatusType;
  skills: string[];
  department_id: string;
  current_call_id: string | null;
  shift_start: string;
  shift_end: string;
  calls_handled_today: number;
  busy_minutes_today: number;
  created_at: string;
}

export interface EscalationItem {
  id: string;
  customer_id: string;
  department_id: string;
  call_id: string;
  caller_number: string;
  caller_name: string;
  priority: EscalationPriorityType;
  status: EscalationStatusType;
  human_agent_id: string | null;
  reason: string;
  ai_summary: string;
  wait_time_seconds: number;
  handle_time_seconds: number;
  created_at: string;
  assigned_at: string | null;
  resolved_at: string | null;
}

export interface StaffingForecastItem {
  id: string;
  customer_id: string;
  date: string;
  hour: number;
  predicted_volume: number;
  predicted_ai_handled: number;
  predicted_escalations: number;
  recommended_staff: number;
  confidence: number;
}

export interface WorkforceMetricsItem {
  id: string;
  customer_id: string;
  period_start: string;
  period_end: string;
  total_calls: number;
  ai_handled: number;
  human_handled: number;
  containment_rate: number;
  avg_wait_time_seconds: number;
  avg_handle_time_seconds: number;
  escalation_rate: number;
  cost_savings_cents: number;
  created_at: string;
}

export interface ROIEstimateItem {
  human_cost_per_month_cents: number;
  ai_cost_per_month_cents: number;
  monthly_savings_cents: number;
  annual_savings_cents: number;
  savings_percentage: number;
  calls_per_month: number;
  containment_rate: number;
}

export interface WorkforceDashboardData {
  active_human_agents: number;
  total_human_agents: number;
  queue_length: number;
  avg_wait_time_seconds: number;
  containment_rate: number;
  containment_trend: Array<{ period: string; containment_rate: number; total_calls: number }>;
  escalation_rate: number;
  cost_savings_this_month_cents: number;
  agents_by_status: Record<string, number>;
  recent_escalations: EscalationItem[];
}

export interface QueueStatusData {
  waiting: number;
  assigned: number;
  resolved_today: number;
  abandoned_today: number;
  avg_wait_time_seconds: number;
  longest_waiting_seconds: number;
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
