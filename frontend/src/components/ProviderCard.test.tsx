import { render, screen } from "@testing-library/react";
import { av, na, noQuota, silentProvider } from "../test-fixtures";
import type { Provider } from "../types/api";
import { ProviderCard } from "./ProviderCard";

test("fournisseur muet : N/A partout, aucune barre de quota (R1)", () => {
  render(<ProviderCard provider={silentProvider} />);
  expect(screen.getAllByText("N/A").length).toBeGreaterThanOrEqual(4); // tokens, latence, coût, quota
  expect(screen.queryByRole("progressbar")).toBeNull();
  expect(screen.getByText("santé N/A")).toBeTruthy();
});

test("quota exposé : barre, pourcentage et temps avant reset", () => {
  const p: Provider = {
    ...silentProvider,
    quota: { ...noQuota, unit: av("tokens"), remaining: av(280), limit: av(1000), used_pct: av(72),
             reset_in_seconds: av(8040) },
  };
  render(<ProviderCard provider={p} />);
  expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("72");
  expect(screen.getByText(/Utilisé 72 %/)).toBeTruthy();
  expect(screen.getByText(/reset dans 2h 14m/)).toBeTruthy();
});

test("restant connu sans pourcentage : pas de barre inventée", () => {
  const p: Provider = { ...silentProvider, quota: { ...noQuota, remaining: av(50) } };
  render(<ProviderCard provider={p} />);
  expect(screen.queryByRole("progressbar")).toBeNull();
  expect(screen.queryByText(/reset dans/)).toBeNull();
});

test("badge de santé", () => {
  const p: Provider = { ...silentProvider, metrics: { ...silentProvider.metrics, health: av("degraded") } };
  render(<ProviderCard provider={p} />);
  expect(screen.getByText("degraded")).toBeTruthy();
  expect(na.available).toBe(false);
});
