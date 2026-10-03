import type { MetricValue } from "../types/metric";

interface Props {
  label: string;
  metric: MetricValue;
  unit?: string;
}

/** R1 : une métrique indisponible affiche « N/A », jamais un chiffre ni une barre fictive. */
export function Metric({ label, metric, unit }: Props) {
  return (
    <div className="cb-card">
      <div className="cb-stat-label">{label}</div>
      {metric.available ? (
        <div className="cb-stat-value">
          {metric.value}
          {unit ? ` ${unit}` : ""}
        </div>
      ) : (
        <span className="cb-na" title="Non exposé par le fournisseur">N/A</span>
      )}
    </div>
  );
}
