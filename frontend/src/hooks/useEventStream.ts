import { useEffect, useRef, useState } from "react";
import { ApiError, api } from "../api";
import type { Severity, UnifiedEvent } from "../types/api";

export type StreamStatus = "connecting" | "open" | "reconnecting" | "unauthorized";
const SEVERITIES: Severity[] = ["info", "low", "medium", "high", "critical"];

/** Validation défensive (R3) : un message qui ne respecte pas le schéma unifié est ignoré. */
export function parseEvent(raw: unknown): UnifiedEvent | null {
  try {
    const v: unknown = typeof raw === "string" ? JSON.parse(raw) : null;
    if (typeof v !== "object" || v === null) return null;
    const e = v as Record<string, unknown>;
    const ok =
      typeof e["id"] === "string" && typeof e["timestamp"] === "string" &&
      typeof e["source"] === "string" && typeof e["agent"] === "string" &&
      typeof e["type"] === "string" && SEVERITIES.includes(e["severity"] as Severity) &&
      typeof e["data"] === "object" && e["data"] !== null &&
      (e["confidence"] === null || typeof e["confidence"] === "number");
    return ok ? (v as UnifiedEvent) : null;
  } catch {
    return null;
  }
}

export function useEventStream(onUnauthorized: () => void, max = 200) {
  const [events, setEvents] = useState<UnifiedEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const unauthRef = useRef(onUnauthorized);
  useEffect(() => {
    unauthRef.current = onUnauthorized;
  });

  useEffect(() => {
    let ws: WebSocket | null = null;
    let stopped = false;
    let attempt = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${window.location.host}/api/ws/events?replay=50`);
      ws.onopen = () => {
        attempt = 0;
        setStatus("open");
      };
      ws.onmessage = (m: MessageEvent<unknown>) => {
        const ev = parseEvent(m.data);
        if (ev) setEvents((prev) => [...prev, ev].slice(-max));
      };
      ws.onclose = () => {
        if (stopped) return;
        setStatus("reconnecting");
        // Un refus de handshake est vu comme une simple coupure : on interroge la session.
        api.me().then(
          () => {
            if (stopped) return;
            timer = setTimeout(connect, Math.min(30_000, 1000 * 2 ** attempt++));
          },
          (e: unknown) => {
            if (stopped) return;
            if (e instanceof ApiError && e.status === 401) {
              setStatus("unauthorized");
              unauthRef.current();
            } else {
              timer = setTimeout(connect, Math.min(30_000, 1000 * 2 ** attempt++));
            }
          },
        );
      };
    };
    connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      ws?.close();
    };
  }, [max]);

  return { events, status };
}
