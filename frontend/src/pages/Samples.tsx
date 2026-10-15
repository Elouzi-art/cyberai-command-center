import { useState } from "react";
import { ApiError, api } from "../api";
import { SampleReport } from "../components/SampleReport";
import { Badge } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import { formatBytes, formatTime } from "../lib/format";
import type { Me, SampleStatus } from "../types/api";

const UPLOAD_ERRORS: Record<number, string> = {
  400: "Fichier vide.",
  403: "Droits insuffisants.",
  413: "Fichier trop volumineux.",
  429: "File d'analyse pleine, réessayez plus tard.",
};
const FAIL_REASONS: Record<string, string> = {
  timeout: "délai d'analyse dépassé",
  crashed: "l'analyseur a planté sur ce fichier",
  out_of_memory: "mémoire insuffisante",
  hash_mismatch: "empreinte différente de celle déposée",
  result_invalid: "résultat de l'analyseur rejeté (non conforme)",
};
const STATUS: Record<SampleStatus, { label: string; tone: "muted" | "green" | "red" }> = {
  queued: { label: "en attente d'analyse", tone: "muted" },
  analyzed: { label: "analysé", tone: "green" },
  failed: { label: "échec", tone: "red" },
};

function Detail({ id, onUnauthorized }: { id: string; onUnauthorized: () => void }) {
  const { data, error } = usePolling(() => api.sample(id), 3_000, onUnauthorized);
  if (error) return <p role="alert" className="cb-field-error">{error}</p>;
  if (!data) return <p className="cb-muted">Chargement…</p>;
  if (data.status === "queued") return <p className="cb-muted">En attente de l'analyseur…</p>;
  if (data.status === "failed")
    return (
      <p role="alert" className="cb-field-error">
        Analyse impossible : {FAIL_REASONS[data.error ?? ""] ?? "erreur de l'analyseur"}.
      </p>
    );
  return data.report ? <SampleReport report={data.report} /> : null;
}

export function Samples({ me, onUnauthorized }: { me: Me; onUnauthorized: () => void }) {
  const { data, error, reload } = usePolling(api.samples, 3_000, onUnauthorized);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  async function upload() {
    if (!file) return;
    setBusy(true);
    setNotice(null);
    try {
      const s = await api.uploadSample(file);
      setSelected(s.id);
      setFile(null);
      setNotice(`« ${s.name} » déposé en quarantaine (${formatBytes(s.size)}).`);
      void reload();
    } catch (e) {
      setNotice(UPLOAD_ERRORS[e instanceof ApiError ? e.status : 0] ?? "Dépôt impossible.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setConfirmDelete(null);
    try {
      await api.deleteSample(id);
      if (selected === id) setSelected(null);
      void reload();
    } catch {
      setNotice("Suppression impossible.");
    }
  }

  if (error) return <p role="alert" className="cb-field-error">{error}</p>;
  if (!data) return <p className="cb-muted">Chargement…</p>;

  return (
    <>
      <div className="cb-card">
        <h2 className="cb-card-title">Déposer un fichier à analyser</h2>
        <p className="cb-muted">
          Le fichier est placé en quarantaine puis analysé statiquement dans un conteneur isolé, sans réseau.
          Il n'est jamais exécuté ni ré-exposé. N'utilisez pas de données confidentielles non autorisées.
        </p>
        <div className="cb-actions">
          <input type="file" aria-label="Fichier à analyser" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <button type="button" className="cb-btn cb-btn-primary cb-btn-sm" disabled={!file || busy}
                  onClick={() => void upload()}>Déposer et analyser</button>
        </div>
        {notice ? <p role="status" className="cb-notice">{notice}</p> : null}
      </div>

      <div className="cb-card cb-section">
        <h2 className="cb-card-title">Échantillons</h2>
        {data.length === 0 ? <p className="cb-muted">Aucun échantillon.</p> : (
          <table className="cb-table">
            <thead><tr><th>Nom</th><th>SHA-256</th><th>Taille</th><th>Statut</th><th>Règles</th><th>Déposé</th><th /></tr></thead>
            <tbody>
              {data.map((s) => (
                <tr key={s.id}>
                  <td className="cb-mono">{s.name}</td>
                  <td className="cb-mono">{s.sha256.slice(0, 12)}…</td>
                  <td>{formatBytes(s.size)}</td>
                  <td><Badge tone={STATUS[s.status].tone}>{STATUS[s.status].label}</Badge></td>
                  <td>{s.rule_hits ?? "—"}</td>
                  <td>{formatTime(s.created_at)} · {s.uploaded_by}</td>
                  <td className="cb-actions">
                    <button type="button" className="cb-btn cb-btn-outline cb-btn-sm"
                            onClick={() => setSelected(s.id)}>Voir</button>
                    {me.role === "admin" ? (
                      confirmDelete === s.id ? (
                        <button type="button" className="cb-btn cb-btn-danger cb-btn-sm"
                                onClick={() => void remove(s.id)}>Confirmer la suppression</button>
                      ) : (
                        <button type="button" className="cb-btn cb-btn-danger cb-btn-sm"
                                onClick={() => setConfirmDelete(s.id)}>Supprimer</button>
                      )
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected ? (
        <div className="cb-card cb-section" aria-label="Rapport">
          <h2 className="cb-card-title">Rapport</h2>
          <Detail key={selected} id={selected} onUnauthorized={onUnauthorized} />
        </div>
      ) : null}
    </>
  );
}
