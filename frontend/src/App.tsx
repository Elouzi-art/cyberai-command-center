import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { usePolling } from "./hooks/usePolling";
import { Layout, type Page } from "./components/Layout";
import { useEventStream } from "./hooks/useEventStream";
import { Agents } from "./pages/Agents";
import { Approvals } from "./pages/Approvals";
import { Login } from "./pages/Login";
import { Overview } from "./pages/Overview";
import { Providers } from "./pages/Providers";
import type { Action, Me } from "./types/api";

const PAGES: Page[] = ["overview", "agents", "providers", "approvals"];

function usePage(): Page {
  const read = (): Page => {
    const id = window.location.hash.replace(/^#\//, "");
    return (PAGES as string[]).includes(id) ? (id as Page) : "overview";
  };
  const [page, setPage] = useState<Page>(read);
  useEffect(() => {
    const on = () => setPage(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return page;
}

/** Compte des actions en attente (badge). Un viewer n'appelle pas l'API : il n'y a pas accès. */
function usePendingCount(role: Me["role"], onUnauthorized: () => void): number {
  const fetchPending = () => (role === "viewer" ? Promise.resolve<Action[]>([]) : api.actions("pending"));
  const { data } = usePolling(fetchPending, 5_000, onUnauthorized);
  return data?.length ?? 0;
}

function Authed({ me, onLoggedOut }: { me: Me; onLoggedOut: () => void }) {
  const requested = usePage();
  // Un viewer n'a pas accès à la file d'approbation : retour à l'overview plutôt qu'une page vide.
  const page: Page = requested === "approvals" && me.role === "viewer" ? "overview" : requested;
  const { events, status } = useEventStream(onLoggedOut);
  const pending = usePendingCount(me.role, onLoggedOut);

  async function logout() {
    await api.logout().catch(() => undefined);
    onLoggedOut();
  }

  return (
    <Layout page={page} me={me} stream={status} pending={pending} onLogout={() => void logout()}>
      {page === "overview" && <Overview events={events} onUnauthorized={onLoggedOut} />}
      {page === "agents" && <Agents me={me} onUnauthorized={onLoggedOut} />}
      {page === "providers" && <Providers onUnauthorized={onLoggedOut} />}
      {page === "approvals" && me.role !== "viewer" && <Approvals me={me} onUnauthorized={onLoggedOut} />}
    </Layout>
  );
}

export default function App() {
  const [me, setMe] = useState<Me | null | undefined>(undefined); // undefined = vérification en cours

  useEffect(() => {
    api.me().then(setMe, () => setMe(null));
  }, []);
  const loggedOut = useCallback(() => setMe(null), []);

  if (me === undefined) return <p className="cb-muted cb-center">Chargement…</p>;
  if (me === null) return <Login onLogin={setMe} />;
  return <Authed me={me} onLoggedOut={loggedOut} />;
}
