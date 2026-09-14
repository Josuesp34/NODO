"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Athlete, Block, Identity, NodoApiClient, NodoApiError, TokenPair, Workout } from "@nodo/api-client";

type StoredSession = TokenPair & { user: Identity };
const storageKey = "nodo.lab.session";
const apiUrl = process.env.NEXT_PUBLIC_NODO_API_URL ?? "http://127.0.0.1:8000/api/v1";

function localDate(value: Date) { return value.toISOString().slice(0, 10); }
function monthRange() { const now = new Date(); return { start: localDate(new Date(now.getFullYear(), now.getMonth(), 1)), end: localDate(new Date(now.getFullYear(), now.getMonth() + 1, 0)) }; }
function errorMessage(error: unknown) { if (error instanceof NodoApiError) { if (error.status === 401) return "Tu sesión expiró. Vuelve a entrar a NODO."; if (error.status === 403) return "Esta cuenta no tiene acceso al modo entrenador."; if (error.status === 404) return "El atleta ya no está disponible para esta cuenta."; if (error.status === 422) return "El rango de fechas no es válido."; return error.message; } return "No fue posible cargar el calendario. Verifica que la API esté activa."; }
function formatDate(value: string) { return new Intl.DateTimeFormat("es-MX", { day: "2-digit", month: "short" }).format(new Date(`${value}T12:00:00`)); }
function formatSport(value: Workout["sport_type"]) { return value === "running" ? "RUN" : value === "cycling" ? "BIKE" : "SWIM"; }

export default function AthleteCalendar() {
  const params = useParams<{ athleteId: string }>();
  const athleteId = Number(params.athleteId);
  const [athlete, setAthlete] = useState<Athlete | null>(null); const [blocks, setBlocks] = useState<Block[]>([]); const [workouts, setWorkouts] = useState<Workout[]>([]); const [range, setRange] = useState(monthRange); const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null);
  const days = useMemo(() => { const start = new Date(`${range.start}T12:00:00`); const end = new Date(`${range.end}T12:00:00`); const values: string[] = []; for (const cursor = new Date(start); cursor <= end; cursor.setDate(cursor.getDate() + 1)) values.push(localDate(cursor)); return values; }, [range]);

  useEffect(() => {
    const raw = window.sessionStorage.getItem(storageKey);
    if (!raw || !Number.isInteger(athleteId) || athleteId < 1) { setError("No se encontró una sesión válida para abrir este atleta."); setLoading(false); return; }
    try {
      const stored = JSON.parse(raw) as StoredSession;
      if (stored.user.role !== "coach") { setError("Esta cuenta no tiene acceso al modo entrenador."); setLoading(false); return; }
      const client = new NodoApiClient(apiUrl, stored.access_token);
      void Promise.all([client.athletes(), client.blocks(athleteId), client.workouts(athleteId, range.start, range.end)]).then(([athletes, nextBlocks, nextWorkouts]) => { setAthlete(athletes.find((item) => item.id === athleteId) ?? null); setBlocks(nextBlocks); setWorkouts(nextWorkouts); if (!athletes.some((item) => item.id === athleteId)) setError("El atleta ya no está disponible para esta cuenta."); }).catch((reason) => setError(errorMessage(reason))).finally(() => setLoading(false));
    } catch { setError("La sesión guardada no es válida. Vuelve a entrar a NODO."); setLoading(false); }
  }, [athleteId, range.end, range.start]);

  function shiftMonth(offset: number) { const current = new Date(`${range.start}T12:00:00`); const next = new Date(current.getFullYear(), current.getMonth() + offset, 1); setLoading(true); setError(null); setRange({ start: localDate(next), end: localDate(new Date(next.getFullYear(), next.getMonth() + 1, 0)) }); }
  const workoutByDay = new Map(workouts.map((workout) => [workout.scheduled_date.slice(0, 10), workout]));
  const monthTitle = new Intl.DateTimeFormat("es-MX", { month: "long", year: "numeric" }).format(new Date(`${range.start}T12:00:00`));

  return <main className="appShell calendarShell"><header className="topbar"><Link className="brand" href="/lab"><span className="brandDot" />NODO<span className="brandSlash">/</span>LAB</Link><Link className="textButton" href="/lab">Volver a atletas <span>↗</span></Link></header>{loading && !athlete && <div className="loading calendarLoading"><span>ABRIENDO CALENDARIO</span></div>}{error && !athlete && <section className="calendarError"><span className="heroKicker"><span>!</span> ACCESS ERROR</span><h1>No pudimos<br /><em>abrir este nodo.</em></h1><p>{error}</p><Link className="primary calendarBack" href="/lab"><span>VOLVER A ATLETAS</span><b>↗</b></Link></section>}{athlete && <><section className="athleteHero"><div><div className="heroKicker"><span>03</span> ATHLETE NODE / CALENDAR</div><h1>{athlete.first_name}<br /><em>{athlete.last_name}.</em></h1><p>{athlete.email}</p></div><div className="athleteIdentity">{athlete.first_name.charAt(0)}{athlete.last_name.charAt(0)}<small>CONNECTED</small></div></section><section className="calendarSection"><div className="calendarHeader"><div><p className="eyebrow">TRAINING PLAN</p><h2>{monthTitle}</h2></div><div className="calendarControls"><button type="button" onClick={() => shiftMonth(-1)} aria-label="Mes anterior">←</button><button type="button" onClick={() => setRange(monthRange())}>HOY</button><button type="button" onClick={() => shiftMonth(1)} aria-label="Mes siguiente">→</button></div></div><div className="calendarGrid">{days.map((day) => { const workout = workoutByDay.get(day); return <div className={`calendarDay ${workout ? "hasWorkout" : ""}`} key={day}><span>{new Intl.DateTimeFormat("es-MX", { weekday: "short" }).format(new Date(`${day}T12:00:00`)).slice(0, 3).toUpperCase()}</span><strong>{day.slice(8, 10)}</strong>{workout && <div className={`workoutChip ${workout.status}`}><b>{formatSport(workout.sport_type)}</b><small>{workout.title}</small></div>}</div>; })}</div><div className="calendarSummary"><span><i className="legendDraft" /> BORRADOR <i className="legendPublished" /> PUBLICADA</span><span>{workouts.length.toString().padStart(2, "0")} SESIONES / {blocks.length.toString().padStart(2, "0")} BLOQUES</span></div></section></>}<footer className="footerLine"><span>NODO TRAINING SYSTEMS / 2026</span><span>CALENDAR / {athlete ? athlete.first_name.toUpperCase() : "LOADING"} <i /></span></footer></main>;
}
