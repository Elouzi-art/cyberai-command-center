import type { MetricValue } from "../types/metric";
import { Stat } from "./ui";
import { Value } from "./ui";

interface Props {
  label: string;
  metric: MetricValue;
  unit?: string;
}

/** R1 : une métrique indisponible affiche « N/A », jamais un chiffre ni une barre fictive. */
export function Metric({ label, metric, unit }: Props) {
  return (
    <Stat label={label}>
      <Value metric={metric} unit={unit} />
    </Stat>
  );
}
