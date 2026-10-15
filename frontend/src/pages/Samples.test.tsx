import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Samples } from "./Samples";
import { reportFixture, sampleDetail, sampleRow } from "../test-fixtures";
import type { Me, SampleDetail, SampleSummary } from "../types/api";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const analyst: Me = { username: "ana", role: "analyst" };
const admin: Me = { username: "root", role: "admin" };

interface Call { url: string; init: RequestInit | undefined }
function stub(opts: { list?: SampleSummary[]; detail?: SampleDetail; post?: () => Response }): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (method !== "GET") calls.push({ url, init });
    if (method === "POST") return Promise.resolve(opts.post ? opts.post() : json(sampleRow({ status: "queued" })));
    if (method === "DELETE") return Promise.resolve(json({ status: "deleted" }));
    if (url.endsWith("/samples")) return Promise.resolve(json(opts.list ?? []));
    return Promise.resolve(opts.detail ? json(opts.detail) : json({}, 404));
  }));
  return calls;
}
afterEach(() => vi.unstubAllGlobals());
const noop = () => {};

async function pick(file: File) {
  fireEvent.change(await screen.findByLabelText("Fichier à analyser"), { target: { files: [file] } });
  fireEvent.click(screen.getByRole("button", { name: "Déposer et analyser" }));
}

test("le dépôt envoie le fichier brut, avec son nom en paramètre, sans multipart", async () => {
  const calls = stub({});
  render(<Samples me={analyst} onUnauthorized={noop} />);
  const file = new File(["MZ\x90"], "mon fichier.exe");
  await pick(file);
  await waitFor(() => expect(calls).toHaveLength(1));
  expect(calls[0]?.url).toBe("/api/samples?filename=mon%20fichier.exe");
  expect(calls[0]?.init?.method).toBe("POST");
  expect(calls[0]?.init?.body).toBe(file);
  expect(calls[0]?.init?.body instanceof FormData).toBe(false);
  expect((calls[0]?.init?.headers as Record<string, string>)["Content-Type"]).toBe("application/octet-stream");
  expect((await screen.findByRole("status")).textContent).toContain("déposé en quarantaine");
});

test("le bouton est inactif sans fichier", async () => {
  stub({});
  render(<Samples me={analyst} onUnauthorized={noop} />);
  const btn = await screen.findByRole("button", { name: "Déposer et analyser" });
  expect((btn as HTMLButtonElement).disabled).toBe(true);
});

test.each([[413, "trop volumineux"], [429, "File d'analyse pleine"], [400, "vide"], [403, "Droits insuffisants"]])(
  "erreur de dépôt %i expliquée", async (status, text) => {
    stub({ post: () => json({ detail: "détail interne" }, status) });
    render(<Samples me={analyst} onUnauthorized={noop} />);
    await pick(new File(["x"], "a.bin"));
    const msg = await screen.findByRole("status");
    expect(msg.textContent).toContain(text);
    expect(document.body.textContent).not.toContain("détail interne");
  },
);

test("échantillon en attente : statut et message clairs", async () => {
  stub({ list: [sampleRow({ status: "queued", rule_hits: null, file_type: null })],
         detail: sampleDetail({ status: "queued", report: null }) });
  render(<Samples me={analyst} onUnauthorized={noop} />);
  expect(await screen.findByText("en attente d'analyse")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Voir" }));
  expect(await screen.findByText("En attente de l'analyseur…")).toBeTruthy();
});

test("rapport : revue humaine, provenance, règles et sections PE", async () => {
  stub({ list: [sampleRow()], detail: sampleDetail() });
  render(<Samples me={analyst} onUnauthorized={noop} />);
  fireEvent.click(await screen.findByRole("button", { name: "Voir" }));
  const note = await screen.findByRole("note");
  expect(note.textContent).toContain("à vérifier par un humain");
  expect(note.textContent).toContain("Aucun verdict");
  expect(screen.getAllByText("DONNÉE OUTIL")).toHaveLength(2);
  expect(screen.getAllByText("RÈGLE")).toHaveLength(1); // seule la règle est marquée, pas le fait
  expect(screen.getByText(/entropie élevée/)).toBeTruthy();
  const table = screen.getByLabelText("Sections PE");
  expect(table.textContent).toContain("UPX1 ← entrée");
  expect(table.textContent).toContain("read write exec");
});

test("fichier non PE : pas de structure inventée", async () => {
  const report = reportFixture({ pe: undefined, items: [] });
  stub({ list: [sampleRow({ file_type: "PDF" })], detail: sampleDetail({ report }) });
  render(<Samples me={analyst} onUnauthorized={noop} />);
  fireEvent.click(await screen.findByRole("button", { name: "Voir" }));
  expect(await screen.findByText(/non applicable à ce fichier/)).toBeTruthy();
  expect(screen.queryByLabelText("Sections PE")).toBeNull();
});

test("contenu hostile du fichier affiché comme du texte, jamais interprété", async () => {
  const evil = "<img src=x onerror=alert(1)>";
  const pe = reportFixture().pe;
  if (!pe) throw new Error("fixture sans structure PE");
  const report = reportFixture({
    pe: { ...pe, sections: [{ name: evil, virtual_size: 1, raw_size: 1, entropy: 1, flags: [] }],
          imports_dlls: [evil] },
    items: [{ provenance: "tool_data", statement: `section ${evil}`, confidence: null, evidence: [evil], source: "pe-rules" }],
  });
  stub({ list: [sampleRow({ name: evil })], detail: sampleDetail({ report }) });
  const { container } = render(<Samples me={analyst} onUnauthorized={noop} />);
  fireEvent.click(await screen.findByRole("button", { name: "Voir" }));
  await screen.findByLabelText("Sections PE");
  expect(container.querySelector("img")).toBeNull();
  expect(screen.getByLabelText("Sections PE").textContent).toContain(evil);
});

test.each([["timeout", "délai d'analyse dépassé"], ["result_invalid", "rejeté (non conforme)"],
           ["inconnu_xyz", "erreur de l'analyseur"]])(
  "échec « %s » expliqué sans détail technique", async (code, text) => {
    stub({ list: [sampleRow({ status: "failed", error: code })],
           detail: sampleDetail({ status: "failed", error: code, report: null }) });
    render(<Samples me={analyst} onUnauthorized={noop} />);
    fireEvent.click(await screen.findByRole("button", { name: "Voir" }));
    expect((await screen.findByRole("alert")).textContent).toContain(text);
  },
);

test("suppression : réservée à l'admin, en deux temps", async () => {
  const calls = stub({ list: [sampleRow()] });
  const { unmount } = render(<Samples me={analyst} onUnauthorized={noop} />);
  await screen.findByText("evil.exe");
  expect(screen.queryByRole("button", { name: "Supprimer" })).toBeNull();
  unmount();
  render(<Samples me={admin} onUnauthorized={noop} />);
  fireEvent.click(await screen.findByRole("button", { name: "Supprimer" }));
  expect(calls).toHaveLength(0); // premier clic : rien n'est supprimé
  fireEvent.click(screen.getByRole("button", { name: "Confirmer la suppression" }));
  await waitFor(() => expect(calls).toHaveLength(1));
  expect(calls[0]?.url).toBe("/api/samples/smp_0123456789abcdef");
  expect(calls[0]?.init?.method).toBe("DELETE");
});
