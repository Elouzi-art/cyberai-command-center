import type { Agent, Provider, Quota } from "./types/api";
import type { MetricValue } from "./types/metric";

export const na: MetricValue = { value: null, available: false };
export const av = (value: number | string): MetricValue => ({ value, available: true });

export const noQuota: Quota = {
  unit: na, remaining: na, limit: na, used_pct: na, reset_at: na, reset_in_seconds: na,
};

export const silentProvider: Provider = {
  id: "cloud", model: "m", data_sensitivity: ["public"], quota: noQuota,
  metrics: {
    model: av("m"), requests: av(0), tokens: na, latency_ms: na, errors: av(0),
    rate_limit: na, quota_remaining: na, reset_time: na, cost: na, health: na,
  },
};

export const demoAgent: Agent = {
  id: "demo", simulated: true, status: "idle", tasks_running: 0, tasks_completed: 2,
  tasks_failed: 1, last_activity: av("2026-10-10T10:00:00+00:00"),
};

export const evt = (over: Record<string, unknown> = {}) =>
  JSON.stringify({
    id: "e1", timestamp: "2026-10-10T10:00:00.000Z", source: "api", agent: "a", type: "api.request",
    severity: "info", data: { provider: "p", model: "m", latency_ms: 12 }, confidence: null, ...over,
  });

import type { Action } from "./types/api";

export const HASH = `sha256:${"a".repeat(64)}`;
export const action = (over: Partial<Action> = {}): Action => ({
  id: "act_1", agent: "demo", tool: "net.scan", params: { target: "198.51.100.1" }, params_hash: HASH,
  risk_level: "L2", required_role: "analyst", justification_ai: "Scan de routine proposé par l'agent.",
  evidence: ["evt_1"], blast_radius: "aucun", rollback: null, status: "pending",
  created_at: "2026-10-10T10:00:00Z", expires_at: "2099-01-01T00:00:00Z", requested_by: "agent:demo",
  requester_kind: "agent", decided_by: null, decided_at: null, executed_at: null, result: null, ...over,
});
