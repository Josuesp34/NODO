"use client";

import { FormEvent, useEffect, useState } from "react";
import { Identity, NodoApiClient, NodoApiError, TokenPair } from "@nodo/api-client";

type StoredSession = TokenPair & { user: Identity };

const storageKey = "nodo.lab.session";
const apiUrl = process.env.NEXT_PUBLIC_NODO_API_URL ?? "http://127.0.0.1:8000/api/v1";

function readSession(): StoredSession | null {
  const value = window.sessionStorage.getItem(storageKey);
  if (!value) return null;
  try { return JSON.parse(value) as StoredSession; } catch {
    window.sessionStorage.removeItem(storageKey);
    return null;
  }
}

function messageFor(error: unknown) {
  if (error instanceof NodoApiError) {
    if (error.status === 401) return "Correo, contraseña o sesión inválidos.";
    if (error.status === 403) return "Esta cuenta no tiene acceso a NODO Lab.";
    return error.message;
  }
  return "No fue posible conectar con NODO. Verifica que la API esté activa.";
}

export default function Home() {
  const [session, setSession] = useState<StoredSession | null>(null);
  const [ready, setReady] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const stored = readSession();
    if (!stored) { setReady(true); return; }
    const previousSession: StoredSession = stored;
    async function restore() {
      try {
        const user = await new NodoApiClient(apiUrl, previousSession.access_token).me();
        const next: StoredSession = { ...previousSession, user };
        window.sessionStorage.setItem(storageKey, JSON.stringify(next));
        setSession(next);
      } catch (firstError) {
        if (!(firstError instanceof NodoApiError) || firstError.status !== 401) {
          window.sessionStorage.removeItem(storageKey);
          setError(messageFor(firstError));
        } else {
          try {
            const tokens = await new NodoApiClient(apiUrl).refresh(previousSession.refresh_token);
            const user = await new NodoApiClient(apiUrl, tokens.access_token).me();
            const next = { ...tokens, user };
            window.sessionStorage.setItem(storageKey, JSON.stringify(next));
            setSession(next);
          } catch { window.sessionStorage.removeItem(storageKey); }
        }
      } finally { setReady(true); }
    }
    void restore();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const tokens = await new NodoApiClient(apiUrl).login(email, password);
      const user = await new NodoApiClient(apiUrl, tokens.access_token).me();
      const next = { ...tokens, user };
      window.sessionStorage.setItem(storageKey, JSON.stringify(next));
      setSession(next);
      setPassword("");
    } catch (loginError) { setError(messageFor(loginError)); } finally { setSubmitting(false); }
  }

  async function signOut() {
    if (session) {
      try { await new NodoApiClient(apiUrl, session.access_token).logout(); } catch { /* La red puede estar inactiva. */ }
    }
    window.sessionStorage.removeItem(storageKey);
    setSession(null);
    setEmail("");
  }

  if (!ready) return <main className="loading">Abriendo NODO Lab…</main>;
  if (session) return (
    <main className="workspace">
      <header><p className="eyebrow">NODO</p><button className="textButton" onClick={signOut}>Cerrar sesión</button></header>
      <section className="welcome"><p className="label">SESIÓN ACTIVA</p><h1>Hola, {session.user.first_name}.</h1><p>{session.user.role === "coach" ? "NODO Lab es tu módulo de planeación. El siguiente corte construirá el calendario y el editor de sesiones." : "Tu espacio NODO mostrará entrenamiento, recuperación y ejecución. La experiencia de atleta sigue en construcción."}</p>{session.user.is_superuser && <p className="adminBadge">Superusuario de desarrollo</p>}</section>
      <section className="nextStep"><span>01</span><div><h2>{session.user.role === "coach" ? "NODO Lab · atletas y calendario" : "Mi NODO · entrenamiento del día"}</h2><p>{session.user.role === "coach" ? "La interfaz ya tiene una sesión real. Falta el endpoint de lista de atletas para mostrar tu equipo." : "El contrato de sesiones publicadas ya existe; la pantalla móvil será el siguiente módulo."}</p></div></section>
    </main>
  );

  return (
    <main className="authPage">
      <section className="intro"><p className="eyebrow">NODO</p><h1>Tu entrenamiento. Tu equipo. Tu progreso.</h1><p>NODO reúne la experiencia del atleta y NODO Lab, el módulo de planeación para entrenadores.</p></section>
      <form className="loginCard" onSubmit={submit}>
        <div><p className="label">ACCESO NODO</p><h2>Inicia sesión</h2></div>
        <label>Correo<input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
        <label>Contraseña<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary" type="submit" disabled={submitting}>{submitting ? "Conectando…" : "Entrar a NODO"}</button>
        <p className="helper">NODO Lab aparece para cuentas de entrenador. Las capacidades múltiples se incorporarán antes de abrir pilotos.</p>
      </form>
    </main>
  );
}
