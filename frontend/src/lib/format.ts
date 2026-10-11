import type { MetricValue } from "../types/metric";

export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
  if (m > 0) return `${m}m ${String(sec).padStart(2, "0")}s`;
  return `${sec}s`;
}

export const formatNumber = (n: number): string => new Intl.NumberFormat("fr-FR").format(n);

export const formatTime = (iso: string): string => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "?" : d.toLocaleTimeString("fr-FR");
};

/** Texte d'une métrique, ou null si elle est indisponible (jamais de valeur de remplacement). */
export function metricNumber(m: MetricValue): number | null {
  return m.available && typeof m.value === "number" ? m.value : null;
}

const str = (v: unknown): string => (typeof v === "string" || typeof v === "number" ? String(v) : "?");

const isMetric = (v: unknown): v is MetricValue =>
  typeof v === "object" && v !== null && "available" in v && "value" in v;

const tokenText = (v: unknown): string =>
  isMetric(v) && v.available && typeof v.value === "number" ? formatNumber(v.value) : "N/A";

export function describeEvent(type: string, data: Record<string, unknown>): string {
  switch (type) {
    case "api.request":
      return `${str(data["provider"])} · ${str(data["model"])} · ${str(data["latency_ms"])} ms`;
    case "token.usage":
      return `entrée ${tokenText(data["input_tokens"])} · sortie ${tokenText(data["output_tokens"])}`;
    case "api.error":
      return `${str(data["provider"])} · ${str(data["error_type"])}`;
    case "rate_limit.warning": {
      const left = data["remaining_time"];
      const reset = typeof left === "number" ? ` · reset dans ${formatDuration(left)}` : "";
      return `${str(data["provider"])} · ${str(data["used_pct"])} % utilisé${reset}`;
    }
    case "action.proposed":
    case "action.approved":
    case "action.rejected":
    case "action.expired":
    case "action.executed":
    case "action.failed":
    case "action.refused":
      return `${str(data["tool"])} · ${str(data["risk_level"])}`;
    case "agent.started":
    case "agent.completed":
    case "agent.failed":
      return `tâche ${str(data["task_id"])}`;
    default:
      return type;
  }
}
