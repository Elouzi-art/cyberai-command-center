import { useState } from "react";
import { ApiError, api } from "../api";
import { formatDuration } from "../lib/format";
import type { Action, Me, Role } from "../types/api";
import { Badge } from "./ui";

const RANK: Record<Role, number> = { viewer: 1, analyst: 2, admin: 3 };
const ERRORS: Record<number, string> = {
  403: "Refusé : droits insuffisants ou auto-approbation interdite.",
  409: "L'action a changé, expiré ou a déjà été traitée. La liste est actualisée.",
};

interface Props {
  action: Action;
  me: Me;
  onDone: (message: string) => void;
}

export function ActionCard({ action: a, me, onDone }: Props) {
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dry, setDry] = useState<Record<string, unknown> | null>(null);
  const canDecide = a.required_role !== null && RANK[me.role] >= RANK[a.required_role];
  const left = Math.round((new Date(a.expires_at).getTime() - Date.now()) / 1000);

  async function run(job: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await job();
    } catch (e) {
      setError(ERRORS[e instanceof ApiError ? e.status : 0] ?? "Action impossible.");
      onDone("");
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  // L'approbation vise EXACTEMENT le hash affiché : si le contenu change, le serveur refuse.
  const approve = (dryRun: boolean) =>
    run(async () => {
      const out = await api.approve(a.id, a.params_hash, dryRun);
      if (dryRun) setDry(out.dry_run_result ?? {});
      else onDone(`Action ${a.tool} approuvée.`);
    });
  const reject = () =>
    run(async () => {
      await api.reject(a.id);
      onDone(`Action ${a.tool} rejetée.`);
    });

  const strong = a.risk_level === "L3";
  return (
    <article className="cb-card cb-action" aria-label={`Action ${a.tool}`}>
      <header className="cb-card-header">
        <strong className="cb-mono">{a.tool}</strong>
        <span>
          <Badge tone={strong ? "red" : "orange"}>{a.risk_level}</Badge>{" "}
          <Badge tone="muted">{a.status}</Badge>
        </span>
      </header>

      <h3 className="cb-subtitle">Commande exacte (ce qui sera exécuté)</h3>
      <pre className="cb-pre" aria-label="Commande brute">{`${a.tool}\n${JSON.stringify(a.params, null, 2)}`}</pre>
      <p className="cb-muted">Empreinte : <code className="cb-mono">{a.params_hash}</code></p>

      <h3 className="cb-subtitle">Justification de l'IA (non vérifiée)</h3>
      <blockquote className="cb-quote">{a.justification_ai ?? "Aucune justification fournie."}</blockquote>
      <dl className="cb-kv">
        <dt>Demandeur</dt><dd>{a.requested_by} ({a.requester_kind === "agent" ? "agent" : "humain"})</dd>
        <dt>Preuves liées</dt><dd className="cb-mono">{a.evidence.length ? a.evidence.join(", ") : "aucune"}</dd>
        <dt>Impact déclaré</dt><dd>{a.blast_radius ?? "non renseigné"}</dd>
        <dt>Rollback</dt><dd className="cb-mono">{a.rollback ?? "aucun"}</dd>
        <dt>Validation requise</dt><dd>{a.required_role ?? "—"}</dd>
        <dt>Expire dans</dt><dd>{left > 0 ? formatDuration(left) : "expirée"}</dd>
      </dl>

      {a.status === "pending" ? (
        <div className="cb-actions">
          <button type="button" className="cb-btn cb-btn-outline cb-btn-sm" disabled={busy || !canDecide}
                  onClick={() => void approve(true)}>Simuler (dry-run)</button>
          {confirming ? (
            <>
              <button type="button" className="cb-btn cb-btn-danger cb-btn-sm" disabled={busy}
                      onClick={() => void approve(false)}>Confirmer l'exécution</button>
              <button type="button" className="cb-btn cb-btn-outline cb-btn-sm"
                      onClick={() => setConfirming(false)}>Annuler</button>
            </>
          ) : (
            <button type="button" className="cb-btn cb-btn-primary cb-btn-sm" disabled={busy || !canDecide}
                    onClick={() => (strong ? setConfirming(true) : void approve(false))}>Approuver</button>
          )}
          <button type="button" className="cb-btn cb-btn-danger cb-btn-sm" disabled={busy}
                  onClick={() => void reject()}>Rejeter</button>
        </div>
      ) : null}
      {a.status === "pending" && !canDecide ? (
        <p className="cb-muted">Réservé au rôle {a.required_role}. Vous pouvez seulement rejeter.</p>
      ) : null}
      {dry ? <pre className="cb-pre" aria-label="Résultat de la simulation">{JSON.stringify(dry, null, 2)}</pre> : null}
      {error ? <p role="alert" className="cb-field-error">{error}</p> : null}
    </article>
  );
}
