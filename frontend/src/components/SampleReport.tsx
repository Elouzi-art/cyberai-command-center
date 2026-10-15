import { formatBytes } from "../lib/format";
import type { MalwareReport, Provenance } from "../types/api";
import { Badge, NA } from "./ui";

const PROVENANCE: Record<Provenance, { label: string; tone: "blue" | "purple" | "orange" | "green" }> = {
  tool_data: { label: "DONNÉE OUTIL", tone: "blue" },
  ml_result: { label: "MODÈLE ML", tone: "green" },
  ai_observation: { label: "OBSERVATION IA", tone: "purple" },
  hypothesis: { label: "HYPOTHÈSE", tone: "orange" },
};

/** Tout texte vient du fichier analysé : rendu en texte par React, jamais interprété. */
export function SampleReport({ report }: { report: MalwareReport }) {
  const { sample: s, pe } = report;
  return (
    <div className="cb-stack">
      {report.needs_human_review ? (
        <p role="note" className="cb-notice">
          Analyse automatique statique : à vérifier par un humain. Aucun verdict n'est émis et rien n'a été exécuté.
        </p>
      ) : null}
      <dl className="cb-kv">
        <dt>Type</dt><dd>{s.file_type}</dd>
        <dt>Taille</dt><dd>{formatBytes(s.size)}</dd>
        <dt>SHA-256</dt><dd className="cb-mono cb-break">{s.sha256}</dd>
        <dt>SHA-1</dt><dd className="cb-mono cb-break">{s.sha1}</dd>
        <dt>MD5</dt><dd className="cb-mono cb-break">{s.md5}</dd>
        <dt>Entropie globale</dt><dd>{s.entropy} / 8</dd>
      </dl>

      <h3 className="cb-subtitle">Constats</h3>
      <ul className="cb-list" aria-label="Constats">
        {report.items.map((i, n) => (
          <li key={n}>
            <Badge tone={PROVENANCE[i.provenance].tone}>{PROVENANCE[i.provenance].label}</Badge>{" "}
            {i.source === "pe-rules" ? <Badge tone="orange">RÈGLE</Badge> : null} {i.statement}
            {i.evidence.length ? <span className="cb-muted cb-mono"> [{i.evidence.join(", ")}]</span> : null}
            {i.confidence !== null ? <span className="cb-muted"> (confiance {i.confidence})</span> : null}
          </li>
        ))}
      </ul>

      <h3 className="cb-subtitle">Structure PE</h3>
      {pe ? (
        <>
          <p className="cb-muted">
            {pe.machine} · {pe.subsystem} · compilé : {pe.timestamp ?? "absent"} · {pe.imports_count} import(s)
            · overlay {formatBytes(pe.overlay_size)} · signature {pe.signed ? "présente (non vérifiée)" : "absente"}
          </p>
          <table className="cb-table" aria-label="Sections PE">
            <thead><tr><th>Section</th><th>Taille virt.</th><th>Taille fichier</th><th>Entropie</th><th>Droits</th></tr></thead>
            <tbody>
              {pe.sections.map((sec, n) => (
                <tr key={n}>
                  <td className="cb-mono">{sec.name}{sec.name === pe.entry_section ? " ← entrée" : ""}</td>
                  <td>{formatBytes(sec.virtual_size)}</td><td>{formatBytes(sec.raw_size)}</td>
                  <td>
                    <span className="cb-bar" aria-hidden="true">
                      <span className={sec.entropy >= 7 ? "cb-bar-fill is-red" : "cb-bar-fill"}
                            style={{ width: `${(sec.entropy / 8) * 100}%` }} />
                    </span>{" "}{sec.entropy}
                  </td>
                  <td className="cb-mono">{sec.flags.join(" ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="cb-muted">
            DLL importées : {pe.imports_dlls.length ? <span className="cb-mono">{pe.imports_dlls.join(", ")}</span> : <NA />}
          </p>
        </>
      ) : (
        <p className="cb-muted">Analyse structurelle PE non applicable à ce fichier.</p>
      )}
      <p className="cb-muted">
        Outils : {Object.entries(report.tool_versions).map(([k, v]) => `${k} ${v}`).join(" · ")}
      </p>
    </div>
  );
}
