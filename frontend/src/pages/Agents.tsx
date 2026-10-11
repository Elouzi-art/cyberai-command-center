import { useState } from "react";
import { api } from "../api";
import { NA, SimulatedBadge, StatusDot } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import { formatTime } from "../lib/format";
import type { Me } from "../types/api";

export function Agents({ me, onUnauthorized }: { me: Me; onUnauthorized: () => void }) {
  const { data, error, reload } = usePolling(api.agents, 3_000, onUnauthorized);
  const [actionError, setActionError] = useState<string | null>(null);
  const canRun = me.role !== "viewer";

  async function run(fail: boolean) {
    setActionError(null);
    try {
      await api.runDemo(fail);
      void reload();
    } catch {
      setActionError("Action impossible (agent de démonstration désactivé ou droits insuffisants).");
    }
  }

  if (error) return <p role="alert" className="cb-field-error">{error}</p>;
  if (!data) return <p className="cb-muted">Chargement…</p>;
  if (data.length === 0)
    return <p className="cb-muted">Aucun agent. Activez l'agent de démonstration avec DEMO_AGENT=true.</p>;

  return (
    <>
      <div className="cb-card">
        <table className="cb-table">
          <thead>
            <tr><th>Agent</th><th>Statut</th><th>En cours</th><th>Terminées</th><th>Échecs</th><th>Dernière activité</th></tr>
          </thead>
          <tbody>
            {data.map((a) => (
              <tr key={a.id}>
                <td className="cb-mono">{a.id} {a.simulated ? <SimulatedBadge /> : null}</td>
                <td><StatusDot on={a.status === "running"} /> {a.status}</td>
                <td>{a.tasks_running}</td><td>{a.tasks_completed}</td><td>{a.tasks_failed}</td>
                <td>{a.last_activity.available ? formatTime(String(a.last_activity.value)) : <NA />}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {canRun ? (
        <p className="cb-actions">
          <button type="button" className="cb-btn cb-btn-blue cb-btn-sm" onClick={() => void run(false)}>
            Lancer une tâche simulée
          </button>
          <button type="button" className="cb-btn cb-btn-danger cb-btn-sm" onClick={() => void run(true)}>
            Simuler un échec
          </button>
        </p>
      ) : null}
      {actionError ? <p role="alert" className="cb-field-error">{actionError}</p> : null}
    </>
  );
}
