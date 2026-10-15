import { describeEvent, formatBytes, formatDuration, metricNumber } from "./format";

test("formatDuration", () => {
  expect(formatDuration(0)).toBe("0s");
  expect(formatDuration(42)).toBe("42s");
  expect(formatDuration(303)).toBe("5m 03s");
  expect(formatDuration(8040)).toBe("2h 14m");
  expect(formatDuration(-5)).toBe("0s");
});

test("metricNumber ne renvoie rien pour une métrique indisponible", () => {
  expect(metricNumber({ value: null, available: false })).toBeNull();
  expect(metricNumber({ value: 5, available: true })).toBe(5);
});

test("describeEvent affiche N/A pour des tokens inconnus (R1)", () => {
  const txt = describeEvent("token.usage", {
    input_tokens: { value: null, available: false },
    output_tokens: { value: 7, available: true },
  });
  expect(txt).toBe("entrée N/A · sortie 7");
});

test("describeEvent n'affiche le reset que s'il est fourni", () => {
  expect(describeEvent("rate_limit.warning", { provider: "p", used_pct: 85 })).not.toContain("reset");
  expect(describeEvent("rate_limit.warning", { provider: "p", used_pct: 85, remaining_time: 300 }))
    .toContain("reset dans 5m 00s");
});

test("describeEvent tolère des données inattendues sans planter", () => {
  expect(describeEvent("api.error", { provider: { x: 1 } })).toBe("? · ?");
});

test("describeEvent : événements d'action sans exposer les paramètres", () => {
  const txt = describeEvent("action.proposed", { tool: "net.scan", risk_level: "L2", params: { secret: "x" } });
  expect(txt).toBe("net.scan · L2");
});

test("formatBytes", () => {
  expect(formatBytes(512)).toBe("512 o");
  expect(formatBytes(2048)).toBe("2.0 Ko");
  expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 Mo");
  expect(formatBytes(-1)).toBe("?");
});

test("describeEvent : événements d'échantillon sans nom de fichier", () => {
  expect(describeEvent("sample.analyzed", { file_type: "PE", rule_hits: 3, name: "secret.exe" })).toBe("PE · 3 règle(s)");
  expect(describeEvent("sample.failed", { error: "timeout" })).toBe("erreur timeout");
});
