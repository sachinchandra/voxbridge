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
