import type {
  Action, ActionStatus, Agent, Me, Provider, SampleDetail, SampleSummary, UsageTokens,
} from "./types/api";

export class ApiError extends Error {
  constructor(public readonly status: number) {
    super(`HTTP ${status}`);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    credentials: "same-origin",
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) throw new ApiError(res.status); // jamais le détail serveur dans l'UI
  return (await res.json()) as T;
}

const post = <T>(path: string, body: unknown): Promise<T> =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

/** Dépôt d'un fichier : corps brut en flux (pas de multipart), nom transmis en paramètre. */
async function uploadSample(file: File): Promise<SampleSummary> {
  const res = await fetch(`/api/samples?filename=${encodeURIComponent(file.name)}`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/octet-stream" },
    body: file,
  });
  if (!res.ok) throw new ApiError(res.status);
  return (await res.json()) as SampleSummary;
}

export const api = {
  me: () => request<Me>("/auth/me"),
  login: (username: string, password: string) => post<Me>("/auth/login", { username, password }),
  logout: () => post<{ status: string }>("/auth/logout", {}),
  providers: () => request<Provider[]>("/providers"),
  agents: () => request<Agent[]>("/agents"),
  usageTokens: () => request<UsageTokens>("/usage/tokens"),
  actions: (status?: ActionStatus) => request<Action[]>(`/actions${status ? `?status=${status}` : ""}`),
  approve: (id: string, paramsHash: string, dryRun: boolean) =>
    post<Action>(`/actions/${encodeURIComponent(id)}/approve`, { params_hash: paramsHash, dry_run: dryRun }),
  reject: (id: string) => post<Action>(`/actions/${encodeURIComponent(id)}/reject`, {}),
  proposeDemo: (tool: string) => post<Action>("/agents/demo/propose", { tool }),
  samples: () => request<SampleSummary[]>("/samples"),
  sample: (id: string) => request<SampleDetail>(`/samples/${encodeURIComponent(id)}`),
  uploadSample,
  deleteSample: (id: string) =>
    request<{ status: string }>(`/samples/${encodeURIComponent(id)}`, { method: "DELETE" }),
  runDemo: (fail: boolean) => post<{ status: string }>("/agents/demo/run", { fail }),
};
