import { api } from "../api";
import { Badge, SimulatedBadge, Stat, Value } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import { describeEvent, formatNumber, formatTime } from "../lib/format";
import type { Severity, UnifiedEvent, WindowName } from "../types/api";

const TONE: Record<Severity, "blue" | "orange" | "red" | "muted"> = {
  info: "muted", low: "blue", medium: "orange", high: "red", critical: "red",
};
const WINDOWS: { id: WindowName; label: string }[] = [
  { id: "1m", label: "1 minute" }, { id: "1h", label: "1 heure" }, { id: "24h", label: "24 heures" },
];

export function Overview({ events, onUnauthorized }: { events: UnifiedEvent[]; onUnauthorized: () => void }) {
  const usage = usePolling(api.usageTokens, 10_000, onUnauthorized);
  const agents = usePolling(api.agents, 5_000, onUnauthorized);
  const providers = usePolling(api.providers, 10_000, onUnauthorized);

  const real = agents.data?.filter((a) => !a.simulated) ?? [];
  const simulated = (agents.data?.length ?? 0) - real.length;
  const w24 = usage.data?.windows["24h"];
  const healthy = providers.data?.filter((p) => p.metrics.health.available && p.metrics.health.value === "ok").length;
  const alerts = events.filter((e) => e.type === "rate_limit.warning").slice(-5).reverse();
  const recent = events.slice(-15).reverse();

  return (
    <>
      <div className="cb-grid-4">
        <Stat label="Agents actifs" hint={simulated ? `+${simulated} simulé non compté` : undefined}>
          {agents.data ? real.filter((a) => a.status === "running").length : "…"}
        </Stat>
        <Stat label="Tâches en cours">{agents.data ? real.reduce((n, a) => n + a.tasks_running, 0) : "…"}</Stat>
        <Stat label="Tokens (24 h)">{w24 ? <Value metric={w24.tokens} fmt={formatNumber} /> : "…"}</Stat>
        <Stat label="Providers sains" hint={providers.data ? `sur ${providers.data.length}` : undefined}>
          {providers.data ? (providers.data.length ? healthy : "N/A") : "…"}
        </Stat>
      </div>

      <div className="cb-card cb-section">
        <h2 className="cb-card-title">Tokens par fenêtre</h2>
        <table className="cb-table">
          <thead><tr><th>Fenêtre</th><th>Requêtes</th><th>Erreurs</th><th>Tokens</th><th>Moy./requête</th></tr></thead>
          <tbody>
            {WINDOWS.map(({ id, label }) => {
              const w = usage.data?.windows[id];
              return (
                <tr key={id}>
                  <td>{label}</td>
                  <td>{w ? formatNumber(w.requests) : "…"}</td>
                  <td>{w ? formatNumber(w.errors) : "…"}</td>
                  <td>{w ? <Value metric={w.tokens} fmt={formatNumber} /> : "…"}</td>
                  <td>{w ? <Value metric={w.avg_tokens_per_request} /> : "…"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="cb-grid-2 cb-section">
        <section className="cb-card" aria-label="Alertes">
          <h2 className="cb-card-title">Alertes de quota</h2>
          {alerts.length === 0 ? <p className="cb-muted">Aucune alerte.</p> : (
            <ul className="cb-list">
              {alerts.map((e) => (
                <li key={e.id}><Badge tone={TONE[e.severity]}>{e.severity}</Badge> {describeEvent(e.type, e.data)}</li>
              ))}
            </ul>
          )}
        </section>
        <section className="cb-card" aria-label="Événements en direct">
          <h2 className="cb-card-title">Événements en direct</h2>
          {recent.length === 0 ? <p className="cb-muted">En attente d'événements…</p> : (
            <ul className="cb-list cb-mono">
              {recent.map((e) => (
                <li key={e.id}>
                  <span className="cb-muted">{formatTime(e.timestamp)}</span> {e.type}{" "}
                  {e.data["simulated"] === true ? <SimulatedBadge /> : null}{" "}
                  <span className="cb-muted">{describeEvent(e.type, e.data)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}
