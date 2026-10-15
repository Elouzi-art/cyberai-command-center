/** Miroir des réponses du backend. Toute métrique non exposée vaut {value: null, available: false} (R1). */
import type { MetricValue } from "./metric";

export interface Quota {
  unit: MetricValue;
  remaining: MetricValue;
  limit: MetricValue;
  used_pct: MetricValue;
  reset_at: MetricValue;
  reset_in_seconds: MetricValue;
}

export interface ProviderMetrics {
  model: MetricValue;
  requests: MetricValue;
  tokens: MetricValue;
  latency_ms: MetricValue;
  errors: MetricValue;
  rate_limit: MetricValue;
  quota_remaining: MetricValue;
  reset_time: MetricValue;
  cost: MetricValue;
  health: MetricValue;
}

export interface Provider {
  id: string;
  model: string;
  data_sensitivity: string[];
  metrics: ProviderMetrics;
  quota: Quota;
}

export interface Agent {
  id: string;
  simulated: boolean;
  status: "running" | "idle";
  tasks_running: number;
  tasks_completed: number;
  tasks_failed: number;
  last_activity: MetricValue;
}

export interface TokenWindow {
  requests: number;
  errors: number;
  tokens: MetricValue;
  avg_tokens_per_request: MetricValue;
}

export type WindowName = "1m" | "1h" | "24h";
export interface UsageTokens {
  windows: Record<WindowName, TokenWindow>;
}

export type Severity = "info" | "low" | "medium" | "high" | "critical";
/** schemas/event.v1.json */
export interface UnifiedEvent {
  id: string;
  timestamp: string;
  source: string;
  agent: string;
  type: string;
  severity: Severity;
  data: Record<string, unknown>;
  confidence: number | null;
}

export type Role = "viewer" | "analyst" | "admin";
export interface Me {
  username: string;
  role: Role;
}

export type RiskLevel = "L0" | "L1" | "L2" | "L3" | "L4";
export type ActionStatus = "pending" | "approved" | "rejected" | "expired" | "executed" | "failed";
/** schemas/approval_action.v1.json */
export interface Action {
  id: string;
  agent: string;
  tool: string;
  params: Record<string, unknown>;
  params_hash: string;
  risk_level: RiskLevel;
  required_role: "analyst" | "admin" | null;
  justification_ai: string | null;
  evidence: string[];
  blast_radius: string | null;
  rollback: string | null;
  status: ActionStatus;
  created_at: string;
  expires_at: string;
  requested_by: string;
  requester_kind: "agent" | "human";
  decided_by: string | null;
  decided_at: string | null;
  executed_at: string | null;
  result: Record<string, unknown> | null;
  dry_run_result?: Record<string, unknown>;
}

export type SampleStatus = "queued" | "analyzed" | "failed";
export interface SampleSummary {
  id: string;
  name: string;
  sha256: string;
  size: number;
  status: SampleStatus;
  error: string | null;
  file_type: string | null;
  rule_hits: number | null;
  created_at: string;
  uploaded_by: string;
  ingested_at: string | null;
}
export type Provenance = "tool_data" | "ml_result" | "ai_observation" | "hypothesis";
export interface ReportItem {
  provenance: Provenance;
  statement: string;
  confidence: number | null;
  evidence: string[];
  source: string;
}
export interface ReportSection {
  name: string;
  virtual_size: number;
  raw_size: number;
  entropy: number;
  flags: ("read" | "write" | "exec")[];
}
/** schemas/analysis_report.v1.json (rapport de l'agent Malware) */
export interface MalwareReport {
  subject: string;
  agent: "malware";
  generated_at: string;
  needs_human_review: boolean;
  sample: { sha256: string; md5: string; sha1: string; size: number; file_type: string; entropy: number };
  pe?: {
    machine: string;
    subsystem: string;
    timestamp: string | null;
    sections: ReportSection[];
    imports_dlls: string[];
    imports_count: number;
    overlay_size: number;
    signed: boolean;
    entry_section: string | null;
  };
  items: ReportItem[];
  tool_versions: Record<string, string>;
}
export interface SampleDetail extends SampleSummary {
  report: MalwareReport | null;
}
