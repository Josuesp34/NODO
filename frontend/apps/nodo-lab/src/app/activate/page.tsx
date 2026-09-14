"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Identity, NodoApiClient, NodoApiError } from "@nodo/api-client";

const storageKey = "nodo.lab.session";
const apiUrl = process.env.NEXT_PUBLIC_NODO_API_URL ?? "http://127.0.0.1:8000/api/v1";
function messageFor(error: unknown) { if (error instanceof NodoApiError) { if (error.status === 400) return "El token de invitación es inválido, expiró o ya fue utilizado."; if (error.status === 422) return "La contraseña debe tener al menos 12 caracteres."; return error.message; } return "No fue posible activar la cuenta. Verifica que la API esté activa."; }

export default function Activate() {
  const router = useRouter(); const [token, setToken] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState<string | null>(null); const [submitting, setSubmitting] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setError(null); setSubmitting(true); try { const client = new NodoApiClient(apiUrl); const tokens = await client.activateAthlete(token.trim(), password); const user = await new NodoApiClient(apiUrl, tokens.access_token).me() as Identity; window.sessionStorage.setItem(storageKey, JSON.stringify({ ...tokens, user })); router.replace("/nodo"); } catch (reason) { setError(messageFor(reason)); } finally { setSubmitting(false); } }
  return <main className="appShell authShell"><div className="orb orbOne" /><div className="orb orbTwo" /><header className="topbar"><Link className="brand" href="/"><span className="brandDot" />NODO</Link><Link className="textButton" href="/login">Ya tengo acceso <span>↗</span></Link></header><section className="registerLayout"><div className="authIntro"><div className="heroKicker"><span>ATHLETE</span> INVITATION ACTIVATION</div><h1>Entra a<br /><em>tu nodo.</em></h1><p>Activa tu cuenta con el token que te compartió tu entrenador y define tu clave personal.</p></div><form className="loginCard" onSubmit={submit}><div className="cardTop"><div><p className="eyebrow">ACTIVATE ACCOUNT / 001</p><h2>Tu cuenta<br />empieza aquí.</h2></div><span className="devBadge">INVITE FLOW</span></div><label><span>TOKEN DE INVITACIÓN</span><input value={token} onChange={(event) => setToken(event.target.value)} placeholder="Pega tu token de desarrollo" required /></label><label><span>CREA TU CLAVE / 12+ CARACTERES</span><input type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={12} required /></label>{error && <p className="error" role="alert"><strong>!</strong>{error}</p>}<button className="primary" type="submit" disabled={submitting}><span>{submitting ? "ACTIVANDO CUENTA" : "ACTIVAR NODO"}</span><b>↗</b></button><p className="helper">Después de activar, entrarás directamente a tu NODO.</p></form></section><footer className="footerLine"><span>NODO TRAINING SYSTEMS / 2026</span><span>ATHLETE ACCESS <i /></span></footer></main>;
}
