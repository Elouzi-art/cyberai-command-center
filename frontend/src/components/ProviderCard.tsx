import { formatDuration, formatNumber } from "../lib/format";
import type { Provider } from "../types/api";
import { Badge, NA, Value } from "./ui";

function Quota({ q }: { q: Provider["quota"] }) {
  const pct = q.used_pct.available && typeof q.used_pct.value === "number" ? q.used_pct.value : null;
  if (!q.remaining.available) return <p className="cb-muted">Quota : <NA /> (non exposé par le fournisseur)</p>;
  const reset =
    q.reset_in_seconds.available && typeof q.reset_in_seconds.value === "number"
      ? formatDuration(q.reset_in_seconds.value)
      : null;
  return (
    <div>
      {pct !== null ? (
        <div className="cb-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100}
             aria-valuenow={pct} aria-label="Quota utilisé">
          <div className={`cb-progress-fill ${pct >= 95 ? "is-red" : pct >= 80 ? "is-orange" : ""}`}
               style={{ width: `${Math.min(100, pct)}%` }} />
        </div>
      ) : null}
      <p className="cb-muted">
        {pct !== null ? `Utilisé ${pct} % · ` : ""}
        restant <Value metric={q.remaining} fmt={formatNumber} unit={q.unit.available ? String(q.unit.value) : undefined} />
        {reset ? ` · reset dans ${reset}` : ""}
      </p>
    </div>
  );
}

export function ProviderCard({ provider: p }: { provider: Provider }) {
  const m = p.metrics;
  const health = m.health.available ? String(m.health.value) : null;
  return (
    <article className="cb-card" aria-label={`Provider ${p.id}`}>
      <header className="cb-card-header">
        <strong className="cb-mono">{p.id}</strong>
        {health === null ? <Badge tone="muted">santé N/A</Badge> : (
          <Badge tone={health === "ok" ? "green" : "red"}>{health}</Badge>
        )}
      </header>
      <dl className="cb-kv">
        <dt>Modèle</dt><dd className="cb-mono"><Value metric={m.model} /></dd>
        <dt>Requêtes</dt><dd><Value metric={m.requests} fmt={formatNumber} /></dd>
        <dt>Latence moy.</dt><dd><Value metric={m.latency_ms} unit="ms" fmt={(v) => String(Math.round(v))} /></dd>
        <dt>Erreurs</dt><dd><Value metric={m.errors} fmt={formatNumber} /></dd>
        <dt>Tokens</dt><dd><Value metric={m.tokens} fmt={formatNumber} /></dd>
        <dt>Coût estimé</dt><dd><Value metric={m.cost} /></dd>
      </dl>
      <Quota q={p.quota} />
      <p className="cb-tags">
        {p.data_sensitivity.map((s) => <Badge key={s} tone={s === "public" ? "blue" : "orange"}>{s}</Badge>)}
      </p>
    </article>
  );
}
