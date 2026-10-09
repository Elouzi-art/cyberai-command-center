import type { ReactNode } from "react";
import type { MetricValue } from "../types/metric";

export const NA = () => (
  <span className="cb-na" title="Non exposé par le fournisseur">
    N/A
  </span>
);

/** Valeur d'une métrique : R1, indisponible => « N/A », jamais un chiffre de remplacement. */
export function Value({ metric, unit, fmt }: { metric: MetricValue; unit?: string; fmt?: (v: number) => string }) {
  if (!metric.available) return <NA />;
  const v = typeof metric.value === "number" && fmt ? fmt(metric.value) : String(metric.value);
  return <>{unit ? `${v} ${unit}` : v}</>;
}

export const Badge = ({ tone, children }: { tone: "green" | "blue" | "orange" | "red" | "muted"; children: ReactNode }) => (
  <span className={`cb-badge cb-badge-${tone}`}>{children}</span>
);

export const SimulatedBadge = () => (
  <span className="cb-badge cb-badge-purple" title="Chiffres simulés, exclus des totaux">
    SIMULÉ
  </span>
);

export const StatusDot = ({ on }: { on: boolean }) => (
  <span className={on ? "cb-status-dot" : "cb-status-dot cb-status-dot-off"} aria-hidden="true" />
);

export function Stat({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <div className="cb-card cb-stat">
      <div className="cb-stat-label">{label}</div>
      <div className="cb-stat-value">{children}</div>
      {hint ? <div className="cb-stat-hint">{hint}</div> : null}
    </div>
  );
}
