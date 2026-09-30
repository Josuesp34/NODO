"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { Brand } from "@/components/ui";

type Step = "request" | "confirm" | "done";

export default function PasswordResetPage() {
  const [step, setStep] = useState<Step>("request");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function send(path: string, body: unknown) {
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(payload?.detail ?? "No se pudo completar la solicitud.");
      }
      setStep(path.endsWith("/request") ? "confirm" : "done");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo completar la solicitud.");
    } finally {
      setSubmitting(false);
    }
  }

  function requestCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void send("/api/session/password-reset/request", { email });
  }

  function confirmCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void send("/api/session/password-reset/confirm", { email, reset_token: code.trim(), password });
  }

  return <main className="auth-page" id="contenido">
    <header className="public-nav"><Brand /><Link className="button button-quiet" href="/login">Volver a acceso</Link></header>
    <div className="auth-wrap">
      <section className="auth-copy"><p className="eyebrow"><strong>ACCESS</strong> Recuperación</p><h1>Vuelve a<br /><em>tu NODO.</em></h1><p className="lead">Recupera el acceso con un código privado. El enlace no lleva tu código en la URL.</p></section>
      {step === "request" ? <form className="auth-card" onSubmit={requestCode}>
        <span className="badge badge-signal">RESET / 001</span><h2>Recupera tu acceso.</h2>
        <label className="field"><span className="field-label">Correo de tu cuenta</span><input className="input" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
        {error ? <div className="alert" role="alert">{error}</div> : null}
        <button className="button button-primary" type="submit" disabled={submitting}>{submitting ? "Enviando…" : "Enviar código ↗"}</button>
        <p className="helper">Si existe una cuenta con ese correo, recibirás instrucciones. El código caduca en 30 minutos.</p>
      </form> : null}
      {step === "confirm" ? <form className="auth-card" onSubmit={confirmCode}>
        <span className="badge badge-signal">RESET / 002</span><h2>Elige una contraseña nueva.</h2>
        <p className="helper">Si existe una cuenta para {email}, revisa su correo. Puedes pedir otro código después de 15 minutos.</p>
        <label className="field"><span className="field-label">Código recibido</span><textarea className="textarea" autoComplete="off" value={code} onChange={(event) => setCode(event.target.value)} required /></label>
        <label className="field"><span className="field-label">Contraseña nueva · mínimo 12 caracteres</span><input className="input" type="password" autoComplete="new-password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
        {error ? <div className="alert" role="alert">{error}</div> : null}
        <button className="button button-primary" type="submit" disabled={submitting}>{submitting ? "Actualizando…" : "Cambiar contraseña ↗"}</button>
      </form> : null}
      {step === "done" ? <section className="auth-card" role="status"><span className="badge badge-signal">ACCESS / READY</span><h2>Contraseña actualizada.</h2><p className="helper">Cerramos todas tus sesiones anteriores. Inicia sesión con tu contraseña nueva.</p><Link className="button button-primary" href="/login">Ir a iniciar sesión ↗</Link></section> : null}
    </div>
  </main>;
}
