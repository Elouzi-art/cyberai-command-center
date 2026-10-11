import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Approvals } from "./Approvals";
import { HASH, action } from "../test-fixtures";
import type { Action, Me } from "../types/api";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const analyst: Me = { username: "ana", role: "analyst" };
const admin: Me = { username: "root", role: "admin" };

type Calls = { url: string; method: string; body: Record<string, unknown> | null }[];
function stub(list: Action[], post: (url: string) => Response = () => json({ status: "ok" })): Calls {
  const calls: Calls = [];
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (method === "GET") return Promise.resolve(json(list));
    calls.push({ url, method, body: init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null });
    return Promise.resolve(post(url));
  }));
  return calls;
}
afterEach(() => vi.unstubAllGlobals());

test("affiche la commande exacte, l'empreinte et une justification IA non vérifiée", async () => {
  stub([action()]);
  render(<Approvals me={analyst} onUnauthorized={() => {}} />);
  const raw = await screen.findByLabelText("Commande brute");
  expect(raw.textContent).toContain("net.scan");
  expect(raw.textContent).toContain("198.51.100.1");
  expect(screen.getByText(HASH)).toBeTruthy();
  expect(screen.getByText("Justification de l'IA (non vérifiée)")).toBeTruthy();
  expect(screen.getByText("Impact déclaré")).toBeTruthy();
});

test("les paramètres sont affichés comme du texte, jamais interprétés", async () => {
  const evil = "<img src=x onerror=alert(1)>";
  stub([action({ params: { target: evil }, justification_ai: evil })]);
  const { container } = render(<Approvals me={analyst} onUnauthorized={() => {}} />);
  await screen.findByLabelText("Commande brute");
  expect(container.querySelector("img")).toBeNull();
  expect(screen.getByLabelText("Commande brute").textContent).toContain(evil);
});

test("approuver (L2) envoie exactement l'empreinte affichée", async () => {
  const calls = stub([action()]);
  render(<Approvals me={analyst} onUnauthorized={() => {}} />);
  fireEvent.click(await screen.findByRole("button", { name: "Approuver" }));
  await waitFor(() => expect(calls).toHaveLength(1));
  expect(calls[0]).toEqual({ url: "/api/actions/act_1/approve", method: "POST",
                             body: { params_hash: HASH, dry_run: false } });
});

test("L3 : confirmation en deux temps avant toute exécution", async () => {
  const calls = stub([action({ risk_level: "L3", required_role: "admin", tool: "firewall.block_ip" })]);
  render(<Approvals me={admin} onUnauthorized={() => {}} />);
  fireEvent.click(await screen.findByRole("button", { name: "Approuver" }));
  expect(calls).toHaveLength(0); // premier clic : rien n'est envoyé
  fireEvent.click(screen.getByRole("button", { name: "Annuler" }));
  expect(screen.getByRole("button", { name: "Approuver" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Approuver" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirmer l'exécution" }));
  await waitFor(() => expect(calls).toHaveLength(1));
  expect(calls[0]?.body).toEqual({ params_hash: HASH, dry_run: false });
});

test("un analyste ne peut pas approuver ni simuler une action L3, seulement rejeter", async () => {
  const calls = stub([action({ risk_level: "L3", required_role: "admin" })]);
  render(<Approvals me={analyst} onUnauthorized={() => {}} />);
  const approve = await screen.findByRole("button", { name: "Approuver" });
  expect((approve as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Simuler (dry-run)" }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText(/Réservé au rôle admin/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Rejeter" }));
  await waitFor(() => expect(calls[0]?.url).toBe("/api/actions/act_1/reject"));
});

test("dry-run : envoie dry_run=true et affiche la simulation", async () => {
  const calls = stub([action()], () => json({ ...action(), dry_run_result: { simulated: true, dry_run: true } }));
  render(<Approvals me={analyst} onUnauthorized={() => {}} />);
  fireEvent.click(await screen.findByRole("button", { name: "Simuler (dry-run)" }));
  expect((await screen.findByLabelText("Résultat de la simulation")).textContent).toContain('"dry_run": true');
  expect(calls[0]?.body).toEqual({ params_hash: HASH, dry_run: true });
});

test.each([[409, /changé, expiré ou a déjà été traitée/], [403, /droits insuffisants ou auto-approbation/]])(
  "erreur %i affichée sans détail serveur", async (status, text) => {
    stub([action()], () => json({ detail: "détail interne secret" }, status));
    render(<Approvals me={analyst} onUnauthorized={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: "Approuver" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(text);
    expect(document.body.textContent).not.toContain("détail interne secret");
  },
);

test("proposition de démonstration L4 : refus de la politique expliqué", async () => {
  stub([], () => json({ detail: "x" }, 403));
  render(<Approvals me={analyst} onUnauthorized={() => {}} />);
  fireEvent.click(await screen.findByRole("button", { name: /suppression de preuve/ }));
  expect((await screen.findByRole("status")).textContent).toContain("Refusée par la politique");
});

test("agent de démonstration désactivé : message dédié", async () => {
  stub([], () => json({}, 404));
  render(<Approvals me={analyst} onUnauthorized={() => {}} />);
  fireEvent.click(await screen.findByRole("button", { name: /scan/ }));
  expect((await screen.findByRole("status")).textContent).toContain("DEMO_AGENT=true");
});

test("décisions récentes listées à part des actions en attente", async () => {
  stub([action(), action({ id: "act_2", status: "executed", decided_by: "root", tool: "host.isolate",
                           decided_at: "2026-10-10T11:00:00Z" })]);
  render(<Approvals me={admin} onUnauthorized={() => {}} />);
  await screen.findByLabelText("Commande brute");
  expect(screen.getByText("Décisions récentes")).toBeTruthy();
  expect(screen.getByText("host.isolate")).toBeTruthy();
  expect(screen.getAllByLabelText("Commande brute")).toHaveLength(1);
});
