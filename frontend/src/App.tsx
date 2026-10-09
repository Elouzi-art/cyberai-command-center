import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { Layout, type Page } from "./components/Layout";
import { useEventStream } from "./hooks/useEventStream";
import { Agents } from "./pages/Agents";
import { Login } from "./pages/Login";
import { Overview } from "./pages/Overview";
import { Providers } from "./pages/Providers";
import type { Me } from "./types/api";

const PAGES: Page[] = ["overview", "agents", "providers"];

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

function Authed({ me, onLoggedOut }: { me: Me; onLoggedOut: () => void }) {
  const page = usePage();
  const { events, status } = useEventStream(onLoggedOut);

  async function logout() {
    await api.logout().catch(() => undefined);
    onLoggedOut();
  }

  return (
    <Layout page={page} me={me} stream={status} onLogout={() => void logout()}>
      {page === "overview" && <Overview events={events} onUnauthorized={onLoggedOut} />}
      {page === "agents" && <Agents me={me} onUnauthorized={onLoggedOut} />}
      {page === "providers" && <Providers onUnauthorized={onLoggedOut} />}
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
