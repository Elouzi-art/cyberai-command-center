import { useState } from "react";
import { ApiError, api } from "../api";
import type { Me } from "../types/api";

export function Login({ onLogin }: { onLogin: (me: Me) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onLogin(await api.login(username, password));
    } catch (err) {
      const status = err instanceof ApiError ? err.status : 0;
      setError(
        status === 401 ? "Identifiants invalides." :
        status === 429 ? "Trop de tentatives. Réessayez plus tard." :
        "Connexion impossible.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="cb-login">
      <form className="cb-card" onSubmit={(e) => void submit(e)} aria-label="Connexion">
        <h1 className="cb-title">Cyber<span className="cb-accent">AI</span> Command Center</h1>
        <label className="cb-form-label" htmlFor="u">Utilisateur</label>
        <input id="u" className="cb-form-input" autoComplete="username" required maxLength={64}
               value={username} onChange={(e) => setUsername(e.target.value)} />
        <label className="cb-form-label" htmlFor="p">Mot de passe</label>
        <input id="p" className="cb-form-input" type="password" autoComplete="current-password" required
               maxLength={256} value={password} onChange={(e) => setPassword(e.target.value)} />
        {error ? <p role="alert" className="cb-field-error">{error}</p> : null}
        <button className="cb-btn cb-btn-primary" type="submit" disabled={busy}>Se connecter</button>
      </form>
    </main>
  );
}
