import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import { action, demoAgent, evt, silentProvider } from "./test-fixtures";

class FakeWS {
  static all: FakeWS[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((m: { data: unknown }) => void) | null = null;
  onclose: (() => void) | null = null;
  constructor(public url: string) {
    FakeWS.all.push(this);
  }
  close() {}
}

const ws0 = (): FakeWS => {
  const w = FakeWS.all[0];
  if (!w) throw new Error("aucune WebSocket ouverte");
  return w;
};

type Routes = Record<string, (init?: RequestInit, url?: string) => Response | Promise<Response>>;
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const usage = {
  windows: Object.fromEntries(
    ["1m", "1h", "24h"].map((w) => [
      w, { requests: 0, errors: 0, tokens: { value: null, available: false },
           avg_tokens_per_request: { value: null, available: false } },
    ]),
  ),
};

function stub(routes: Routes) {
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    const handler = routes[url.replace(/^\/api/, "").split("?")[0] ?? ""];
    return Promise.resolve(handler ? handler(init, url) : json({}, 404));
  }));
}
const base = (role: string): Routes => ({
  "/auth/me": () => json({ username: "ana", role }),
  "/agents": () => json([demoAgent]),
  "/providers": () => json([]),
  "/usage/tokens": () => json(usage),
  "/auth/logout": () => json({ status: "ok" }),
  "/actions": () => json([]),
});

beforeEach(() => {
  FakeWS.all = [];
  window.location.hash = "";
  vi.stubGlobal("WebSocket", FakeWS);
});
afterEach(() => vi.unstubAllGlobals());

test("sans session : formulaire de connexion, erreur générique sans fuite", async () => {
  stub({ "/auth/me": () => json({}, 401), "/auth/login": () => json({}, 401) });
  render(<App />);
  fireEvent.change(await screen.findByLabelText("Utilisateur"), { target: { value: "ana" } });
  fireEvent.change(screen.getByLabelText("Mot de passe"), { target: { value: "secret-pass-123" } });
  fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));
  expect((await screen.findByRole("alert")).textContent).toBe("Identifiants invalides.");
  expect(document.body.textContent).not.toContain("secret-pass-123");
});

test("trop de tentatives : message dédié", async () => {
  stub({ "/auth/me": () => json({}, 401), "/auth/login": () => json({}, 429) });
  render(<App />);
  fireEvent.change(await screen.findByLabelText("Utilisateur"), { target: { value: "a" } });
  fireEvent.change(screen.getByLabelText("Mot de passe"), { target: { value: "b" } });
  fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Trop de tentatives");
});

test("overview : agent simulé non compté, tokens et providers en N/A (R1)", async () => {
  stub(base("viewer"));
  render(<App />);
  expect(await screen.findByText("+1 simulé non compté")).toBeTruthy();
  await waitFor(() => expect(screen.getAllByText("N/A").length).toBeGreaterThanOrEqual(4));
  expect(screen.getByLabelText("Alertes")).toBeTruthy();
});

test("événement simulé reçu en direct : étiqueté SIMULÉ", async () => {
  stub(base("viewer"));
  render(<App />);
  await screen.findByText("Agents actifs");
  act(() => {
    ws0().onopen?.();
    ws0().onmessage?.({
      data: evt({ type: "token.usage", data: { simulated: true, input_tokens: { value: 100, available: true },
                                               output_tokens: { value: 40, available: true } } }),
    });
  });
  const live = screen.getByLabelText("Événements en direct");
  expect(live.textContent).toContain("SIMULÉ");
  expect(live.textContent).toContain("entrée 100 · sortie 40");
});

test("alerte de quota affichée sans champ inventé", async () => {
  stub(base("viewer"));
  render(<App />);
  await screen.findByText("Agents actifs");
  act(() => {
    ws0().onmessage?.({
      data: evt({ type: "rate_limit.warning", severity: "medium", data: { provider: "cloud", used_pct: 85 } }),
    });
  });
  const alerts = screen.getByLabelText("Alertes");
  expect(alerts.textContent).toContain("cloud · 85 % utilisé");
  expect(alerts.textContent).not.toContain("reset");
});

test("page Agents : un viewer ne voit pas les actions, un analyste oui", async () => {
  window.location.hash = "#/agents";
  stub(base("viewer"));
  const { unmount } = render(<App />);
  await screen.findByText("SIMULÉ");
  expect(screen.queryByText("Lancer une tâche simulée")).toBeNull();
  unmount();
  stub(base("analyst"));
  render(<App />);
  expect(await screen.findByText("Lancer une tâche simulée")).toBeTruthy();
});

test("page Providers : fournisseur muet en N/A", async () => {
  window.location.hash = "#/providers";
  stub({ ...base("viewer"), "/providers": () => json([silentProvider]) });
  render(<App />);
  expect(await screen.findByText("santé N/A")).toBeTruthy();
  expect(screen.queryByRole("progressbar")).toBeNull();
});

test("401 pendant la navigation : retour à la connexion", async () => {
  stub({ ...base("viewer"), "/agents": () => json({}, 401) });
  render(<App />);
  expect(await screen.findByLabelText("Utilisateur")).toBeTruthy();
});

test("déconnexion", async () => {
  stub(base("viewer"));
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "Déconnexion" }));
  expect(await screen.findByLabelText("Utilisateur")).toBeTruthy();
});

test("badge Approvals : nombre d'actions en attente, visible pour un analyste", async () => {
  stub({ ...base("analyst"), "/actions": () => json([action(), action({ id: "act_2" })]) });
  render(<App />);
  expect((await screen.findByLabelText("2 en attente")).textContent).toBe("2");
  expect(screen.getByRole("link", { name: /Approvals/ })).toBeTruthy();
});

test("un viewer n'a ni l'onglet Approvals ni accès à la file", async () => {
  window.location.hash = "#/approvals";
  stub(base("viewer"));
  render(<App />);
  await screen.findByText("Agents actifs");
  expect(screen.queryByRole("link", { name: /Approvals/ })).toBeNull();
  const calls = (fetch as unknown as { mock: { calls: string[][] } }).mock.calls.map((c) => c[0] ?? "");
  expect(calls.some((u) => u.includes("/actions"))).toBe(false);
});
