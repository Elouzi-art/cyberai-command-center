import type { ReactNode } from "react";
import type { StreamStatus } from "../hooks/useEventStream";
import type { Me } from "../types/api";
import { Badge, StatusDot } from "./ui";

export type Page = "overview" | "agents" | "providers";
const NAV: { id: Page; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "agents", label: "Agents" },
  { id: "providers", label: "Providers" },
];
const STREAM_LABEL: Record<StreamStatus, string> = {
  connecting: "connexion…", open: "temps réel", reconnecting: "reconnexion…", unauthorized: "session expirée",
};

interface Props {
  page: Page;
  me: Me;
  stream: StreamStatus;
  onLogout: () => void;
  children: ReactNode;
}

export function Layout({ page, me, stream, onLogout, children }: Props) {
  return (
    <div className="cb-layout">
      <aside className="cb-sidebar">
        <div className="cb-brand">
          <span className="cb-brand-name">Cyber<span>AI</span></span>
        </div>
        <nav aria-label="Navigation principale">
          {NAV.map((n) => (
            <a key={n.id} href={`#/${n.id}`} className={n.id === page ? "cb-nav-link active" : "cb-nav-link"}
               aria-current={n.id === page ? "page" : undefined}>
              {n.label}
            </a>
          ))}
        </nav>
        <div className="cb-sidebar-footer">
          <div className="cb-user-name">{me.username}</div>
          <div className="cb-user-role">{me.role}</div>
          <button type="button" className="cb-btn cb-btn-outline cb-btn-sm" onClick={onLogout}>Déconnexion</button>
        </div>
      </aside>
      <div className="cb-main">
        <header className="cb-topbar">
          <h1 className="cb-title">{NAV.find((n) => n.id === page)?.label}</h1>
          <Badge tone={stream === "open" ? "green" : "muted"}>
            <StatusDot on={stream === "open"} /> {STREAM_LABEL[stream]}
          </Badge>
        </header>
        <main className="cb-content">{children}</main>
      </div>
    </div>
  );
}
