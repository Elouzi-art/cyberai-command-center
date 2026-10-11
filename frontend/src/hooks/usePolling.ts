import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api";

export function usePolling<T>(fetcher: () => Promise<T>, intervalMs: number, onUnauthorized: () => void) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fetcherRef = useRef(fetcher);
  const unauthRef = useRef(onUnauthorized);
  useEffect(() => {
    fetcherRef.current = fetcher;
    unauthRef.current = onUnauthorized;
  });

  const load = useCallback(async () => {
    try {
      setData(await fetcherRef.current());
      setError(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) unauthRef.current();
      else setError("Données indisponibles");
    }
  }, []);

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), intervalMs);
    return () => clearInterval(t);
  }, [load, intervalMs]);

  return { data, error, reload: load };
}
