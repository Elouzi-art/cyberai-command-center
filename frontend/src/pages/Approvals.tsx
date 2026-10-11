import { useState } from "react";
import { ApiError, api } from "../api";
import { ActionCard } from "../components/ActionCard";
import { Badge } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import { formatTime } from "../lib/format";
import type { Me } from "../types/api";

const DEMO = [
  { tool: "net.scan", label: "Proposer un scan (L2)" },
  { tool: "firewall.block_ip", label: "Proposer un blocage IP (L3)" },
  { tool: "evidence.delete", label: "Proposer une suppression de preuve (L4, doit être refusée)" },
];

export function Approvals({ me, onUnauthorized }: { me: Me; onUnauthorized: () => void }) {
  const { data, error, reload } = usePolling(() => api.actions(), 3_000, onUnauthorized);
  const [notice, setNotice] = useState<string | null>(null);

  async function demo(tool: string) {
    try {
      await api.proposeDemo(tool);
      setNotice("Action de démonstration proposée.");
      void reload();
    } catch (e) {
      const s = e instanceof ApiError ? e.status : 0;
      setNotice(
        s === 403 ? "Refusée par la politique (niveau L4 : jamais exécutable)." :
        s === 404 ? "Agent de démonstration désactivé (DEMO_AGENT=true)." : "Proposition impossible.",
      );
    }
  }

  if (error) return <p role="alert" className="cb-field-error">{error}</p>;
  if (!data) return <p className="cb-muted">Chargement…</p>;
  const pending = data.filter((a) => a.status === "pending");
  const recent = data.filter((a) => a.status !== "pending").slice(0, 10);

  return (
    <>
      {notice ? <p role="status" className="cb-notice">{notice}</p> : null}
      <p className="cb-muted">
        Aucune action de niveau L2 ou plus ne s'exécute sans validation humaine. Vérifiez la commande
        exacte ci-dessous : la justification de l'IA n'est pas une preuve.
      </p>
      {pending.length === 0 ? <p className="cb-muted cb-section">Aucune action en attente.</p> : (
        <div className="cb-stack cb-section">
          {pending.map((a) => <ActionCard key={a.id} action={a} me={me} onDone={(m) => { if (m) setNotice(m); void reload(); }} />)}
        </div>
      )}

      {recent.length > 0 ? (
        <div className="cb-card cb-section">
          <h2 className="cb-card-title">Décisions récentes</h2>
          <table className="cb-table">
            <thead><tr><th>Outil</th><th>Niveau</th><th>Statut</th><th>Décidé par</th><th>Heure</th></tr></thead>
            <tbody>
              {recent.map((a) => (
                <tr key={a.id}>
                  <td className="cb-mono">{a.tool}</td><td><Badge tone="muted">{a.risk_level}</Badge></td>
                  <td>{a.status}</td><td>{a.decided_by ?? "—"}</td>
                  <td>{a.decided_at ? formatTime(a.decided_at) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <div className="cb-card cb-section">
        <h2 className="cb-card-title">Agent de démonstration</h2>
        <div className="cb-actions">
          {DEMO.map((d) => (
            <button key={d.tool} type="button" className="cb-btn cb-btn-blue cb-btn-sm"
                    onClick={() => void demo(d.tool)}>{d.label}</button>
          ))}
        </div>
      </div>
    </>
  );
}
