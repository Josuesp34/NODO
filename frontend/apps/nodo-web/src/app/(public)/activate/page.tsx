"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Brand } from "@/components/ui";

export default function ActivatePage() {
  const router = useRouter();
  const [form, setForm] = useState({ invitation_token: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSubmitting(true); setError(null);
    try {
      const response = await fetch("/api/session/activate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
      if (!response.ok) {
        const payload = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(response.status === 400 ? "La invitación expiró, ya se utilizó o no es válida." : payload?.detail ?? "No fue posible activar la cuenta.");
      }
      router.replace("/athlete/today"); router.refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No fue posible activar la cuenta."); }
    finally { setSubmitting(false); }
  }
  return <main className="auth-page" id="contenido"><header className="public-nav"><Brand /><Link className="button button-quiet" href="/login">Ya tengo acceso</Link></header><div className="auth-wrap"><section className="auth-copy"><p className="eyebrow"><strong>ATHLETE</strong> Invitación</p><h1>Entra a<br /><em>tu NODO.</em></h1><p className="lead">Activa tu cuenta con el código recibido por correo o compartido por tu entrenador y crea una contraseña personal.</p></section><form className="auth-card" onSubmit={submit}><span className="badge badge-signal">ACTIVATE / 001</span><h2>Tu cuenta empieza aquí.</h2><label className="field"><span className="field-label">Código de invitación</span><textarea className="textarea" autoComplete="off" value={form.invitation_token} onChange={(event) => setForm({ ...form, invitation_token: event.target.value.trim() })} required /></label><label className="field"><span className="field-label">Contraseña · mínimo 12 caracteres</span><input className="input" type="password" autoComplete="new-password" minLength={12} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /></label>{error ? <div className="alert" role="alert">{error}</div> : null}<button className="button button-primary" type="submit" disabled={submitting}>{submitting ? "Activando…" : "Activar mi NODO ↗"}</button><p className="helper">El código se envía únicamente en el cuerpo de la solicitud; no se guarda en la URL.</p></form></div></main>;
}
