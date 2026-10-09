import { act, renderHook } from "@testing-library/react";
import { evt } from "../test-fixtures";
import { useEventStream } from "./useEventStream";

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

const meStub = (status: number) =>
  vi.fn(() => Promise.resolve(new Response(JSON.stringify({ username: "u", role: "viewer" }), { status })));

beforeEach(() => {
  FakeWS.all = [];
  vi.stubGlobal("WebSocket", FakeWS);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

test("reçoit les événements valides et ignore ceux qui violent le schéma (R3)", () => {
  const { result } = renderHook(() => useEventStream(() => {}));
  const ws = ws0();
  expect(ws.url).toContain("/api/ws/events");
  act(() => {
    ws.onopen?.();
    ws.onmessage?.({ data: evt() });
    ws.onmessage?.({ data: "pas du json" });
    ws.onmessage?.({ data: evt({ severity: "catastrophe" }) });
    ws.onmessage?.({ data: evt({ data: null }) });
  });
  expect(result.current.status).toBe("open");
  expect(result.current.events).toHaveLength(1);
});

test("conserve au plus `max` événements", () => {
  const { result } = renderHook(() => useEventStream(() => {}, 3));
  act(() => {
    for (let i = 0; i < 5; i++) ws0().onmessage?.({ data: evt({ id: `e${i}` }) });
  });
  expect(result.current.events.map((e) => e.id)).toEqual(["e2", "e3", "e4"]);
});

test("session expirée : arrêt sans reconnexion et notification", async () => {
  vi.stubGlobal("fetch", meStub(401));
  const onUnauthorized = vi.fn();
  const { result } = renderHook(() => useEventStream(onUnauthorized));
  await act(async () => {
    ws0().onclose?.();
  });
  expect(result.current.status).toBe("unauthorized");
  expect(onUnauthorized).toHaveBeenCalledOnce();
  expect(FakeWS.all).toHaveLength(1);
});

test("coupure réseau avec session valide : reconnexion avec délai", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch", meStub(200));
  const onUnauthorized = vi.fn();
  const { result } = renderHook(() => useEventStream(onUnauthorized));
  await act(async () => {
    ws0().onclose?.();
  });
  expect(result.current.status).toBe("reconnecting");
  expect(FakeWS.all).toHaveLength(1);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1100);
  });
  expect(FakeWS.all).toHaveLength(2);
  expect(onUnauthorized).not.toHaveBeenCalled();
});

test("le démontage ferme sans reconnecter", async () => {
  vi.stubGlobal("fetch", meStub(200));
  const { unmount } = renderHook(() => useEventStream(() => {}));
  const ws = ws0();
  unmount();
  await act(async () => {
    ws.onclose?.();
  });
  expect(FakeWS.all).toHaveLength(1);
});

test.each(["id", "timestamp", "source", "agent", "type", "severity", "data", "confidence"])(
  "un événement sans le champ « %s » est rejeté (R3)",
  (field) => {
    const { result } = renderHook(() => useEventStream(() => {}));
    const full = JSON.parse(evt()) as Record<string, unknown>;
    const incomplete = Object.fromEntries(Object.entries(full).filter(([k]) => k !== field));
    act(() => {
      ws0().onmessage?.({ data: JSON.stringify(incomplete) });
    });
    expect(result.current.events).toHaveLength(0);
  },
);

test("un champ de mauvais type est rejeté (R3)", () => {
  const { result } = renderHook(() => useEventStream(() => {}));
  act(() => {
    ws0().onmessage?.({ data: evt({ id: 42 }) });
    ws0().onmessage?.({ data: evt({ confidence: "haute" }) });
    ws0().onmessage?.({ data: evt({ type: null }) });
  });
  expect(result.current.events).toHaveLength(0);
});
