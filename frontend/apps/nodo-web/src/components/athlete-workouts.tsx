"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSession } from "./product-shell";
import { EmptyState, ErrorState, PageHeader, StatusBadge } from "./ui";
import { WorkoutView } from "./workout-view";
import { nodoRequest, problemFrom } from "@/lib/api";
import { addDays, formatDay, isoDay, weekRange } from "@/lib/dates";
import { readWorkouts, saveWorkouts } from "@/lib/offline-store";
import type { Workout } from "@/lib/contracts";

export function TodayWorkspace() {
  const { identity } = useSession();
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [cachedAt, setCachedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const today = isoDay();

  function load() {
    const range = { start: addDays(today, -1), end: addDays(today, 7) };
    setLoading(true); setError(null);
    void nodoRequest<Workout[]>(`athletes/${identity.id}/workouts?start=${range.start}&end=${range.end}`).then((items) => {
      const published = items.filter((item) => item.status === "published"); setWorkouts(published); saveWorkouts(identity.id, published); setCachedAt(null);
    }).catch((reason) => {
      const cached = readWorkouts(identity.id);
      if (cached) { setWorkouts(cached.workouts); setCachedAt(cached.savedAt); }
      else setError(problemFrom(reason).message);
    }).finally(() => setLoading(false));
  }
  useEffect(load, [identity.id]);
  const todayWorkouts = workouts.filter((item) => item.scheduled_date.slice(0, 10) === today);
  const next = workouts.find((item) => item.scheduled_date.slice(0, 10) > today);

  return <div className="page page-narrow"><PageHeader eyebrow="Mi NODO / Hoy" title={`Hola, ${identity.first_name}.`} description="Tu plan del día, sin ruido. Sólo aparecen sesiones publicadas para esta cuenta." actions={<Link className="button" href="/athlete/week">Ver semana</Link>} />{cachedAt ? <div className="offline-banner" role="status">Mostrando la última copia guardada · {new Intl.DateTimeFormat("es-MX", { dateStyle: "medium", timeStyle: "short" }).format(new Date(cachedAt))}</div> : null}{error ? <ErrorState message={error} retry={load} /> : null}{loading ? <div className="card" role="status">Buscando tu sesión publicada…</div> : todayWorkouts.length ? <div className="stack">{todayWorkouts.map((workout) => <div key={workout.id}><WorkoutView workout={workout} /><div className="cluster" style={{ marginTop: 12 }}><Link className="button button-primary" href={`/athlete/workouts/${workout.id}`}>Abrir sesión completa ↗</Link><Link className="button" href="/athlete/check-in">Registrar cómo me siento</Link></div></div>)}</div> : !error ? <EmptyState title="Hoy no hay una sesión publicada." copy={next ? `Tu siguiente sesión está programada para ${formatDay(next.scheduled_date, { weekday: "long", day: "numeric", month: "long" })}.` : "Cuando tu entrenador publique una sesión, aparecerá aquí. La ausencia de sesión no se interpreta como incumplimiento."} action={<Link className="button" href="/athlete/week">Revisar semana</Link>} /> : null}</div>;
}

export function WeekWorkspace() {
  const { identity } = useSession();
  const [anchor, setAnchor] = useState(isoDay());
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const range = useMemo(() => weekRange(anchor), [anchor]);
  useEffect(() => { setLoading(true); setError(null); void nodoRequest<Workout[]>(`athletes/${identity.id}/workouts?start=${range.start}&end=${range.end}`).then((items) => setWorkouts(items.filter((item) => item.status === "published"))).catch((reason) => setError(problemFrom(reason).message)).finally(() => setLoading(false)); }, [identity.id, range.end, range.start]);
  const days = Array.from({ length: 7 }, (_, index) => addDays(range.start, index));
  return <div className="page page-narrow"><PageHeader eyebrow="Mi NODO / Semana" title="Tu semana" description={`${formatDay(range.start, { day: "numeric", month: "short" })} — ${formatDay(range.end, { day: "numeric", month: "short", year: "numeric" })}`} actions={<><button className="button icon-button" onClick={() => setAnchor(addDays(anchor, -7))}>←</button><button className="button" onClick={() => setAnchor(isoDay())}>Hoy</button><button className="button icon-button" onClick={() => setAnchor(addDays(anchor, 7))}>→</button></>} />{error ? <ErrorState message={error} /> : null}{loading ? <div className="card">Actualizando semana…</div> : <div className="stack">{days.map((day) => { const daily = workouts.filter((item) => item.scheduled_date.slice(0, 10) === day); return <section className="card" key={day}><div className="cluster" style={{ justifyContent: "space-between" }}><strong>{formatDay(day, { weekday: "long", day: "numeric", month: "short" })}</strong>{day === isoDay() ? <StatusBadge tone="signal">Hoy</StatusBadge> : null}</div>{daily.length ? daily.map((workout) => <Link className={`workout-chip published`} href={`/athlete/workouts/${workout.id}`} key={workout.id}><span>{workout.title}</span><small>{workout.sport_type} · abrir detalle</small></Link>) : <p className="helper">Sin sesión publicada.</p>}</section>; })}</div>}</div>;
}

export function WorkoutDetail({ workoutId }: { workoutId: number }) {
  const { identity } = useSession();
  const [workout, setWorkout] = useState<Workout | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const cached = readWorkouts(identity.id)?.workouts.find((item) => item.id === workoutId && item.status === "published"); if (cached) setWorkout(cached);
    void nodoRequest<Workout[]>(`athletes/${identity.id}/workouts?start=${addDays(isoDay(), -366)}&end=${addDays(isoDay(), 366)}`).then((items) => { const found = items.find((item) => item.id === workoutId && item.status === "published"); if (!found) throw new Error("La sesión no está disponible o todavía no fue publicada."); setWorkout(found); }).catch((reason) => setError(reason instanceof Error ? reason.message : problemFrom(reason).message));
  }, [identity.id, workoutId]);
  return <div className="page page-narrow"><PageHeader eyebrow="Mi NODO / Sesión" title={workout?.title ?? "Entrenamiento"} actions={<Link className="button" href="/athlete/week">Volver a la semana</Link>} />{error && !workout ? <ErrorState message={error} /> : workout ? <WorkoutView workout={workout} /> : <div className="card">Abriendo sesión…</div>}</div>;
}
