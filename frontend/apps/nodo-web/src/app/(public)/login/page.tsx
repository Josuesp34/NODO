"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Brand } from "@/components/ui";
import { clearOfflineData } from "@/lib/offline-store";

export default function LoginPage() {
  const router = useRouter();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    void fetch("/api/session/me", { cache: "no-store" }).then((response) => {
      if (response.ok) router.replace("/app");
    });
  }, [router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(null); setSubmitting(true); clearOfflineData();
    try {
      const response = await fetch("/api/session/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
      if (!response.ok) {
        const payload = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(response.status === 401 ? "Correo o contraseña incorrectos." : payload?.detail ?? "No fue posible iniciar sesión.");
      }
      const requested = new URLSearchParams(window.location.search).get("next");
      router.replace(requested?.startsWith("/") ? requested : "/app");
      router.refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No fue posible iniciar sesión."); }
    finally { setSubmitting(false); }
  }

  return <main className="auth-page" id="contenido"><header className="public-nav"><Brand /><Link className="button button-quiet" href="/">Volver</Link></header><div className="auth-wrap"><section className="auth-copy"><p className="eyebrow"><strong>01</strong> Acceso seguro</p><h1>Vuelve a<br /><em>tu ritmo.</em></h1><p className="lead">Tu equipo, tu sesión de hoy y la siguiente decisión viven en el mismo lugar.</p></section><form className="auth-card" onSubmit={submit}><span className="badge badge-signal">ACCESS NODE / 001</span><h2>Entra a NODO.</h2><label className="field"><span className="field-label">Correo</span><input className="input" type="email" autoComplete="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /></label><label className="field"><span className="field-label">Contraseña</span><input className="input" type="password" autoComplete="current-password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /></label>{error ? <div className="alert" role="alert">{error}</div> : null}<button className="button button-primary" type="submit" disabled={submitting}>{submitting ? "Validando…" : "Entrar a NODO ↗"}</button><p className="helper">La sesión se protege en una cookie httpOnly. El navegador no puede leer tus credenciales de acceso.</p><Link className="muted" href="/password-reset">Olvidé mi contraseña</Link><Link className="muted" href="/activate">Tengo una invitación de atleta</Link></form></div></main>;
}
