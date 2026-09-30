"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { clearOfflineData, observeOfflineInvalidation, readActiveWorkouts, type CachedWorkouts } from "@/lib/offline-store";
import { WorkoutView } from "./workout-view";

export function OfflineWorkspace() {
  const [copy, setCopy] = useState<CachedWorkouts | null>(null);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    const initial = readActiveWorkouts(); setCopy(initial); setLoaded(true);
    const unsubscribe = observeOfflineInvalidation(() => setCopy(null));
    const expire = () => { if (initial && Date.parse(initial.expiresAt) <= Date.now()) { clearOfflineData(); setCopy(null); } };
    const timer = initial ? window.setTimeout(expire, Math.max(0, Date.parse(initial.expiresAt) - Date.now())) : undefined;
    window.addEventListener("focus", expire); document.addEventListener("visibilitychange", expire);
    return () => { unsubscribe(); window.clearTimeout(timer); window.removeEventListener("focus", expire); document.removeEventListener("visibilitychange", expire); };
  }, []);
  return <section className="page page-narrow" aria-label="Plan guardado sin conexión"><h1>Tu plan sin conexión</h1><p>Esta copia de lectura caduca a las 24 horas. No incluye chats ni permite registrar cambios. Conéctate para comprobar publicaciones y permisos vigentes.</p>{!loaded ? <p role="status">Buscando una copia guardada…</p> : copy ? <><p className="offline-banner" role="status">Copia del {new Intl.DateTimeFormat("es-MX", { dateStyle: "medium", timeStyle: "short", timeZone: copy.timezone }).format(new Date(copy.savedAt))} · {copy.timezone}</p><div className="stack">{copy.workouts.length ? copy.workouts.map((workout) => <WorkoutView key={workout.id} workout={workout} />) : <p>No hay sesiones guardadas.</p>}</div><button className="button" onClick={() => { clearOfflineData(); setCopy(null); }}>Borrar copia de este dispositivo</button></> : <p>No hay una copia vigente. Abre Hoy o Semana con conexión para guardar tu plan.</p>}<p><Link className="button button-primary" href="/app">Reintentar con conexión</Link></p></section>;
}
