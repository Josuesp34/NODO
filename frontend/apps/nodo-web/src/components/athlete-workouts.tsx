"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSession } from "./product-shell";
import { EmptyState, ErrorState, PageHeader, StatusBadge } from "./ui";
import { WorkoutView } from "./workout-view";
import { nodoRequest, problemFrom } from "@/lib/api";
import { addDays, dayInZone, formatDay, weekRange } from "@/lib/dates";
import { readWorkouts, saveWorkouts } from "@/lib/offline-store";
import type { Workout } from "@/lib/contracts";

export function TodayWorkspace() {
  const { identity } = useSession();
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [cachedAt, setCachedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const today = dayInZone(new Date(), identity.timezone);

  function load() {
    const range = { start: addDays(today, -1), end: addDays(today, 7) };
    setLoading(true); setError(null);
    void nodoRequest<Workout[]>(`athletes/${identity.id}/workouts?start=${range.start}&end=${range.end}`).then((items) => {
      const published = items.filter((item) => item.status === "published"); setWorkouts(published); saveWorkouts(identity.id, published, identity.timezone); setCachedAt(null);
    }).catch((reason) => {
      const cached = reason instanceof TypeError ? readWorkouts(identity.id) : null;
      if (cached) { setWorkouts(cached.workouts); setCachedAt(cached.savedAt); }
      else { setWorkouts([]); setError(problemFrom(reason).message); }
    }).finally(() => setLoading(false));
  }
  useEffect(load, [identity.id]);
  const todayWorkouts = workouts.filter((item) => dayInZone(item.scheduled_date, identity.timezone) === today);
  const next = workouts.find((item) => dayInZone(item.scheduled_date, identity.timezone) > today);

  return <div className="page page-narrow"><PageHeader eyebrow="Mi NODO / Hoy" title={`Hola, ${identity.first_name}.`} description="Tu plan del día, sin ruido. Sólo aparecen sesiones publicadas para esta cuenta." actions={<Link className="button" href="/athlete/week">Ver semana</Link>} />{cachedAt ? <div className="offline-banner" role="status">Mostrando la última copia guardada · {new Intl.DateTimeFormat("es-MX", { dateStyle: "medium", timeStyle: "short" }).format(new Date(cachedAt))}</div> : null}{error ? <ErrorState message={error} retry={load} /> : null}{loading ? <div className="card" role="status">Buscando tu sesión publicada…</div> : todayWorkouts.length ? <div className="stack">{todayWorkouts.map((workout) => <div key={workout.id}><WorkoutView workout={workout} /><div className="cluster" style={{ marginTop: 12 }}><Link className="button button-primary" href={`/athlete/workouts/${workout.id}`}>Abrir sesión completa ↗</Link><Link className="button" href="/athlete/check-in">Registrar cómo me siento</Link></div></div>)}</div> : !error ? <EmptyState title="Hoy no hay una sesión publicada." copy={next ? `Tu siguiente sesión está programada para ${formatDay(next.scheduled_date, { weekday: "long", day: "numeric", month: "long" })}.` : "Cuando tu entrenador publique una sesión, aparecerá aquí. La ausencia de sesión no se interpreta como incumplimiento."} action={<Link className="button" href="/athlete/week">Revisar semana</Link>} /> : null}</div>;
}

export function WeekWorkspace() {
  const { identity } = useSession();
  const [cachedAt, setCachedAt] = useState<string | null>(null);
  const [anchor, setAnchor] = useState(dayInZone(new Date(), identity.timezone));
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const range = useMemo(() => weekRange(anchor), [anchor]);
  useEffect(() => { setLoading(true); setError(null); void nodoRequest<Workout[]>(`athletes/${identity.id}/workouts?start=${range.start}&end=${range.end}`).then((items) => { const published = items.filter((item) => item.status === "published"); setWorkouts(published); saveWorkouts(identity.id, published, identity.timezone); setCachedAt(null); }).catch((reason) => { const copy = reason instanceof TypeError ? readWorkouts(identity.id) : null; if (copy) { setWorkouts(copy.workouts); setCachedAt(copy.savedAt); } else { setWorkouts([]); setError(problemFrom(reason).message); } }).finally(() => setLoading(false)); }, [identity.id, range.end, range.start]);
  const days = Array.from({ length: 7 }, (_, index) => addDays(range.start, index));
  return <div className="page page-narrow"><PageHeader eyebrow="Mi NODO / Semana" title="Tu semana" description={`${formatDay(range.start, { day: "numeric", month: "short" })} — ${formatDay(range.end, { day: "numeric", month: "short", year: "numeric" })}`} actions={<><button className="button icon-button" onClick={() => setAnchor(addDays(anchor, -7))}>←</button><button className="button" onClick={() => setAnchor(dayInZone(new Date(), identity.timezone))}>Hoy</button><button className="button icon-button" onClick={() => setAnchor(addDays(anchor, 7))}>→</button></>} />{cachedAt ? <p className="offline-banner" role="status">Copia guardada · {cachedAt}</p> : null}{error ? <ErrorState message={error} /> : null}{loading ? <div className="card">Actualizando semana…</div> : <div className="stack">{days.map((day) => { const daily = workouts.filter((item) => dayInZone(item.scheduled_date, identity.timezone) === day); return <section className="card" key={day}><div className="cluster" style={{ justifyContent: "space-between" }}><strong>{formatDay(day, { weekday: "long", day: "numeric", month: "short" })}</strong>{day === dayInZone(new Date(), identity.timezone) ? <StatusBadge tone="signal">Hoy</StatusBadge> : null}</div>{daily.length ? daily.map((workout) => <Link className={`workout-chip published`} href={`/athlete/workouts/${workout.id}`} key={workout.id}><span>{workout.title}</span><small>{workout.sport_type} · abrir detalle</small></Link>) : <p className="helper">Sin sesión publicada.</p>}</section>; })}</div>}</div>;
}

export function WorkoutDetail({ workoutId }: { workoutId: number }) {
  const { identity } = useSession();
  const [workout, setWorkout] = useState<Workout | null>(null);
  const [cachedAt, setCachedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setWorkout(null); setError(null); setCachedAt(null);
    void nodoRequest<Workout[]>(`athletes/${identity.id}/workouts?start=${addDays(dayInZone(new Date(), identity.timezone), -366)}&end=${addDays(dayInZone(new Date(), identity.timezone), 366)}`).then((items) => { const found = items.find((item) => item.id === workoutId && item.status === "published"); if (!found) throw new Error("La sesión no está disponible o todavía no fue publicada."); setWorkout(found); }).catch((reason) => { const copy = reason instanceof TypeError ? readWorkouts(identity.id) : null; const saved = copy?.workouts.find((item) => item.id === workoutId && item.status === "published"); if (saved && copy) { setWorkout(saved); setCachedAt(copy.savedAt); } else { setWorkout(null); setError(reason instanceof Error ? reason.message : problemFrom(reason).message); } });
  }, [identity.id, workoutId]);
  return <div className="page page-narrow"><PageHeader eyebrow="Mi NODO / Sesión" title={workout?.title ?? "Entrenamiento"} actions={<Link className="button" href="/athlete/week">Volver a la semana</Link>} />{cachedAt ? <p className="offline-banner" role="status">Copia guardada · {cachedAt}</p> : null}{error && !workout ? <ErrorState message={error} /> : workout ? <WorkoutView workout={workout} /> : <div className="card">Abriendo sesión…</div>}</div>;
}
