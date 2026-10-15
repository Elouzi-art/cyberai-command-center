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

import type { MalwareReport, SampleDetail, SampleSummary } from "./types/api";

export const sampleRow = (over: Partial<SampleSummary> = {}): SampleSummary => ({
  id: "smp_0123456789abcdef", name: "evil.exe", sha256: "ab".repeat(32), size: 2048, status: "analyzed",
  error: null, file_type: "PE", rule_hits: 2, created_at: "2026-10-14T09:00:00Z",
  uploaded_by: "ana", ingested_at: "2026-10-14T09:00:05Z", ...over,
});

export const reportFixture = (over: Partial<MalwareReport> = {}): MalwareReport => ({
  subject: "smp_0123456789abcdef", agent: "malware", generated_at: "2026-10-14T09:00:05+00:00",
  needs_human_review: true,
  sample: { sha256: "ab".repeat(32), md5: "cd".repeat(16), sha1: "ef".repeat(20), size: 2048,
            file_type: "PE", entropy: 6.1 },
  pe: {
    machine: "IMAGE_FILE_MACHINE_AMD64", subsystem: "IMAGE_SUBSYSTEM_WINDOWS_CUI", timestamp: null,
    sections: [
      { name: ".text", virtual_size: 4096, raw_size: 2048, entropy: 7.6, flags: ["read", "exec"] },
      { name: "UPX1", virtual_size: 600, raw_size: 512, entropy: 3.2, flags: ["read", "write", "exec"] },
    ],
    imports_dlls: ["kernel32.dll"], imports_count: 2, overlay_size: 0, signed: false, entry_section: "UPX1",
  },
  items: [
    { provenance: "tool_data", statement: "Entropie globale : 6.1 (sur 8).", confidence: null, evidence: [], source: "entropy" },
    { provenance: "tool_data", statement: "Règle : entropie élevée (7.6 ≥ 7.0).", confidence: null,
      evidence: ["section:.text"], source: "pe-rules" },
  ],
  tool_versions: { pefile: "2024.8.26" }, ...over,
});

export const sampleDetail = (over: Partial<SampleDetail> = {}): SampleDetail => ({
  ...sampleRow(), report: reportFixture(), ...over,
});
