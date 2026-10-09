import type { Agent, Me, Provider, UsageTokens } from "./types/api";

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

export const api = {
  me: () => request<Me>("/auth/me"),
  login: (username: string, password: string) => post<Me>("/auth/login", { username, password }),
  logout: () => post<{ status: string }>("/auth/logout", {}),
  providers: () => request<Provider[]>("/providers"),
  agents: () => request<Agent[]>("/agents"),
  usageTokens: () => request<UsageTokens>("/usage/tokens"),
  runDemo: (fail: boolean) => post<{ status: string }>("/agents/demo/run", { fail }),
};
