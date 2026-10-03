import { Metric } from "./components/Metric";

export default function App() {
  return (
    <main style={{ padding: 24 }}>
      <h1 style={{ fontFamily: "var(--font-mono)" }}>
        Cyber<span style={{ color: "var(--accent)" }}>AI</span> Command Center
      </h1>
      <p style={{ color: "var(--text-secondary)", marginBottom: 16 }}>Sprint 0 — squelette.</p>
      <Metric label="Quota restant" metric={{ value: null, available: false }} />
    </main>
  );
}
