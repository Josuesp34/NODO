"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Athlete, Identity, NodoApiClient, NodoApiError, TokenPair } from "@nodo/api-client";

type StoredSession = TokenPair & { user: Identity };
const storageKey = "nodo.lab.session";
const apiUrl = process.env.NEXT_PUBLIC_NODO_API_URL ?? "http://127.0.0.1:8000/api/v1";

function errorMessage(error: unknown) {
  if (error instanceof NodoApiError) {
    if (error.status === 401) return "Tu sesión expiró. Vuelve a entrar a NODO.";
    if (error.status === 403) return "Esta cuenta no tiene acceso al modo entrenador.";
    return error.message;
  }
  return "No fue posible cargar tus atletas. Verifica que la API esté activa.";
}

export default function LabModule() {
  const [athletes, setAthletes] = useState<Athlete[]>([]);
  const [coach, setCoach] = useState<Identity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const raw = window.sessionStorage.getItem(storageKey);
    if (!raw) { setError("Tu sesión no está disponible. Vuelve a entrar a NODO."); setLoading(false); return; }
    try {
      const stored = JSON.parse(raw) as StoredSession;
      setCoach(stored.user);
      if (stored.user.role !== "coach") { setError("Esta cuenta no tiene acceso al modo entrenador."); setLoading(false); return; }
      void new NodoApiClient(apiUrl, stored.access_token).athletes().then(setAthletes).catch((reason) => setError(errorMessage(reason))).finally(() => setLoading(false));
    } catch { setError("La sesión guardada no es válida. Vuelve a entrar a NODO."); setLoading(false); }
  }, []);

  return <main className="appShell labShell"><header className="topbar"><Link className="brand" href="/nodo"><span className="brandDot" />NODO<span className="brandSlash">/</span>LAB</Link><div className="nodoNav"><span className="labMode">COACH MODE</span><Link className="textButton" href="/nodo">Volver a NODO <span>↗</span></Link></div></header><section className="labHero labHeroCompact"><div className="heroKicker"><span>02</span> COACH MODE / NODO LAB</div><h1>Tu equipo.<br /><em>Tu dirección.</em></h1><p>Selecciona un atleta para comenzar a planear su siguiente bloque de entrenamiento.</p></section><section className="athleteSection"><div className="sectionHeading"><div><p className="eyebrow">ATHLETE INDEX</p><h2>Atletas <span>({loading ? "—" : athletes.length.toString().padStart(2, "0")})</span></h2></div><span className="sectionRule" /></div>{loading && <div className="labState"><span className="loadingPulse" /> CARGANDO EQUIPO</div>}{error && <div className="labState labError"><strong>!</strong><span>{error}</span><Link href="/login">Volver al acceso ↗</Link></div>}{!loading && !error && athletes.length === 0 && <div className="emptyState"><span className="emptyGlyph">＋</span><div><h3>Aún no hay atletas.</h3><p>Las invitaciones se habilitarán desde este centro de mando cuando conectemos el siguiente flujo.</p></div></div>}{!loading && !error && athletes.length > 0 && <div className="athleteGrid">{athletes.map((athlete, index) => <article className="athleteCard" key={athlete.id}><div className="athleteTop"><span className="athleteIndex">{String(index + 1).padStart(2, "0")}</span><span className="athleteStatus">CONNECTED</span></div><div className="athleteInitials">{athlete.first_name.charAt(0)}{athlete.last_name.charAt(0)}</div><h3>{athlete.first_name} {athlete.last_name}</h3><p>{athlete.email}</p><button type="button" className="athleteAction" disabled aria-disabled="true">ABRIR PERFIL <span>↗</span></button></article>)}</div>}</section><footer className="footerLine"><span>NODO TRAINING SYSTEMS / 2026</span><span>{coach?.first_name ? `${coach.first_name.toUpperCase()} / COACH` : "LAB / IN BUILD"} <i /></span></footer></main>;
}
