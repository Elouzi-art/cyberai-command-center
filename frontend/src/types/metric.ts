/** Miroir de schemas/provider_metric.v1.json (R1). */
export type MetricValue =
  | { value: number | string; available: true }
  | { value: null; available: false };
