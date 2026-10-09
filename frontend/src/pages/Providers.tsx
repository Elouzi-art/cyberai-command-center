import { api } from "../api";
import { ProviderCard } from "../components/ProviderCard";
import { usePolling } from "../hooks/usePolling";

export function Providers({ onUnauthorized }: { onUnauthorized: () => void }) {
  const { data, error } = usePolling(api.providers, 10_000, onUnauthorized);
  if (error) return <p role="alert" className="cb-field-error">{error}</p>;
  if (!data) return <p className="cb-muted">Chargement…</p>;
  if (data.length === 0)
    return <p className="cb-muted">Aucun provider actif. Activez-en un dans config.yaml (enabled: true).</p>;
  return (
    <div className="cb-grid-2">
      {data.map((p) => <ProviderCard key={p.id} provider={p} />)}
    </div>
  );
}
