import { render, screen } from "@testing-library/react";
import { Metric } from "./Metric";

test("affiche N/A quand la métrique est indisponible (R1)", () => {
  render(<Metric label="Quota restant" metric={{ value: null, available: false }} />);
  expect(screen.getByText("N/A")).toBeTruthy();
});

test("affiche la valeur quand disponible", () => {
  render(<Metric label="Tokens" metric={{ value: 1200, available: true }} unit="tok" />);
  expect(screen.getByText("1200 tok")).toBeTruthy();
});
