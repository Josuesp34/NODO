"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { nodoRequest, problemFrom } from "@/lib/api";
import { addDays, isoDay } from "@/lib/dates";
import type { Workout } from "@/lib/contracts";
import { useSession } from "./product-shell";
import { EmptyState, ErrorState, PageHeader, StatusBadge } from "./ui";

type Activity = {
  id: number;
  sport_type: string;
  local_date: string;
  timezone: string;
  duration_sec: number;
  distance_m: number | null;
  trimp: number | null;
  tss: number | null;
  provider: string;
  quality: string;
  version: number;
  prescribed_workout_id: number | null;
};
type Lap = {
  index: number;
  duration_sec: number | null;
  distance_m: number | null;
  avg_heart_rate: number | null;
  avg_power: number | null;
};
type Detail = Activity & { laps: Lap[]; telemetry_points: number };
type Measure = {
  unit: string;
  planned: number | null;
  actual: number | null;
  delta: number | null;
};
type ComparedLap = {
  index: number;
  kind: string;
  measure: Measure;
  target?: {
    unit: string;
    minimum: number;
    maximum: number;
    actual: number | null;
    in_range: boolean | null;
  };
};
type Comparison = {
  timezone: string;
  workouts: {
    workout_id: number;
    title: string;
    local_date: string;
    sport_type: string;
    status: string;
    quality?: string;
    reason: string;
    summary: Measure[];
    laps: ComparedLap[];
  }[];
  daily_load: {
    local_date: string;
    value: number | null;
    unit: string;
    quality: string;
    formula_version: string;
  }[];
};
const stateLabel: Record<string, string> = {
  comparable: "Comparación disponible",
  insufficient_data: "Datos insuficientes",
  not_synchronized: "Sin actividad vinculada",
  incompatible_discipline: "Disciplinas sin comparación directa",
  ambiguous_multiple_activities: "Varias actividades vinculadas",
};
const sports: Record<string, string> = {
  running: "Carrera",
  cycling: "Ciclismo",
  swimming: "Natación",
  triathlon: "Triatlón",
  unknown: "Deporte no informado",
};
const measured = (value: number | null, unit: string) =>
  value === null ? "Sin dato" : `${Math.round(value * 100) / 100} ${unit}`;

export function ActivitiesWorkspace({
  athleteId,
  coach = false,
}: {
  athleteId?: number;
  coach?: boolean;
}) {
  const { identity } = useSession();
  const id = athleteId ?? identity.id;
  const [page, setPage] = useState<{
    items: Activity[];
    total: number;
    next_offset: number | null;
  } | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [start, setStart] = useState(addDays(isoDay(), -27));
  const [end, setEnd] = useState(isoDay());
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [loading, setLoading] = useState(false);
  function load() {
    setLoading(true);
    setError(null);
    void nodoRequest<typeof page>(
      `athletes/${id}/activities/page?offset=${offset}&limit=20`,
    )
      .then(setPage)
      .catch((reason) => setError(problemFrom(reason).message))
      .finally(() => setLoading(false));
  }
  useEffect(load, [id, offset]);
  async function compare() {
    setError(null);
    setLoading(true);
    try {
      setComparison(
        await nodoRequest<Comparison>(
          `athletes/${id}/activities/comparison?start=${start}&end=${end}`,
        ),
      );
    } catch (reason) {
      setError(problemFrom(reason).message);
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="page">
      <PageHeader
        eyebrow={coach ? "NODO Lab / Actividades" : "Mi NODO / Actividades"}
        title="Historial y comparación"
        description="Revisa los datos recibidos y confirma a qué sesión corresponden. La falta de datos no equivale a incumplimiento."
        actions={
          coach ? (
            <Link className="button" href={`/coach/athletes/${id}/calendar`}>
              Calendario
            </Link>
          ) : (
            <Link className="button" href="/athlete/connections">
              Importar FIT
            </Link>
          )
        }
      />
      {error ? <ErrorState message={error} retry={load} /> : null}
      {loading ? <p role="status">Cargando datos…</p> : null}
      {page?.items.length ? (
        <section className="stack">
          {page.items.map((item) => (
            <article className="card" key={item.id}>
              <div className="cluster">
                <StatusBadge>
                  {sports[item.sport_type] ?? item.sport_type}
                </StatusBadge>
                <span>
                  {item.local_date} · {item.timezone}
                </span>
                <StatusBadge>{item.provider}</StatusBadge>
              </div>
              <p>
                {measured(item.duration_sec, "s")} ·{" "}
                {measured(item.distance_m, "m")} · TRIMP{" "}
                {item.trimp ?? "sin dato"}
              </p>
              <p className="helper">
                {item.prescribed_workout_id
                  ? "Sesión vinculada"
                  : "Vínculo pendiente"}{" "}
                ·{" "}
                {item.quality === "partial"
                  ? "Datos parciales"
                  : "Resumen recibido"}
              </p>
              <button className="button" onClick={() => setDetailId(item.id)}>
                Detalle y vínculo
              </button>
            </article>
          ))}
          <div className="cluster">
            <button
              className="button"
              disabled={offset === 0 || loading}
              onClick={() => setOffset(Math.max(0, offset - 20))}
            >
              Anterior
            </button>
            <span>
              {offset + 1}–{Math.min(offset + 20, page.total)} de {page.total}
            </span>
            <button
              className="button"
              disabled={page.next_offset === null || loading}
              onClick={() => setOffset(page.next_offset ?? offset)}
            >
              Siguiente
            </button>
          </div>
        </section>
      ) : !loading && page ? (
        <EmptyState
          title="Todavía no hay actividades."
          copy="El plan manual está disponible. Los datos aparecerán al importar un FIT o sincronizar el proveedor."
        />
      ) : null}
      {detailId !== null ? (
        <section style={{ marginTop: 18 }}>
          <button className="button" onClick={() => setDetailId(null)}>
            Cerrar detalle
          </button>
          <ActivityDetailWorkspace
            athleteId={id}
            activityId={detailId}
            onLinked={load}
            embedded
          />
        </section>
      ) : null}
      <section className="card stack" style={{ marginTop: 18 }}>
        <h2>Plan y ejecución</h2>
        <div className="form-grid">
          <label className="field">
            Desde
            <input
              className="input"
              type="date"
              value={start}
              onChange={(event) => setStart(event.target.value)}
            />
          </label>
          <label className="field">
            Hasta
            <input
              className="input"
              type="date"
              value={end}
              onChange={(event) => setEnd(event.target.value)}
            />
          </label>
        </div>
        <button
          className="button button-primary"
          disabled={loading || end < start}
          onClick={compare}
        >
          Comparar período
        </button>
        {comparison ? (
          <>
            <p className="helper">
              Días en {comparison.timezone}. Los laps se alinean únicamente
              cuando coincide su cantidad con los pasos; revisa la segmentación.
            </p>
            {comparison.workouts.length ? (
              comparison.workouts.map((row) => (
                <article className="card stack" key={row.workout_id}>
                  <div className="cluster">
                    <StatusBadge>
                      {stateLabel[row.status] ?? row.status}
                    </StatusBadge>
                    <span>
                      {row.local_date} · {sports[row.sport_type]}
                    </span>
                  </div>
                  <h3>{row.title}</h3>
                  <p className="helper">{row.reason}</p>
                  {row.summary.map((item) => (
                    <p key={item.unit}>
                      Plan: {measured(item.planned, item.unit)} · observado:{" "}
                      {measured(item.actual, item.unit)} · diferencia:{" "}
                      {measured(item.delta, item.unit)}
                    </p>
                  ))}
                  {row.laps.map((lap) => (
                    <p key={lap.index}>
                      Lap {lap.index + 1}:{" "}
                      {measured(lap.measure.actual, lap.measure.unit)} /{" "}
                      {measured(lap.measure.planned, lap.measure.unit)}
                      {lap.target
                        ? ` · objetivo ${lap.target.minimum}–${lap.target.maximum} ${lap.target.unit}: ${measured(lap.target.actual, lap.target.unit)}`
                        : ""}
                    </p>
                  ))}
                </article>
              ))
            ) : (
              <p>No hay sesiones publicadas en este período.</p>
            )}
            <details>
              <summary>Carga por día y calidad</summary>
              {comparison.daily_load.map((day) => (
                <p key={`${day.local_date}-${day.unit}`}>
                  {day.local_date}: {measured(day.value, day.unit)} ·{" "}
                  {day.quality === "not_observed"
                    ? "Sin observación; no se interpreta como descanso confirmado"
                    : "Carga registrada"}{" "}
                  · {day.formula_version}
                </p>
              ))}
            </details>
          </>
        ) : null}
      </section>
    </div>
  );
}

export function ActivityDetailWorkspace({
  athleteId,
  activityId,
  onLinked,
  embedded = false,
}: {
  athleteId?: number;
  activityId: number;
  onLinked?: () => void;
  embedded?: boolean;
}) {
  const { identity } = useSession();
  const id = athleteId ?? identity.id;
  const [detail, setDetail] = useState<Detail | null>(null);
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  function load() {
    setError(null);
    void nodoRequest<Detail>(`athletes/${id}/activities/${activityId}`)
      .then(async (item) => {
        setDetail(item);
        setSelected(item.prescribed_workout_id?.toString() ?? "");
        setWorkouts(
          await nodoRequest<Workout[]>(
            `athletes/${id}/workouts?start=${addDays(item.local_date, -7)}&end=${addDays(item.local_date, 7)}`,
          ),
        );
      })
      .catch((reason) => setError(problemFrom(reason).message));
  }
  useEffect(load, [id, activityId]);
  async function link() {
    if (!detail) return;
    setError(null);
    setMessage(null);
    setBusy(true);
    try {
      await nodoRequest(`athletes/${id}/activities/${activityId}/link`, {
        method: "PUT",
        body: {
          prescribed_workout_id: selected ? Number(selected) : null,
          expected_version: detail.version,
        },
      });
      load();
      onLinked?.();
      setMessage("Vínculo guardado en el servidor.");
    } catch (reason) {
      setError(
        problemFrom(reason).status === 409
          ? "El vínculo cambió. Recarga antes de guardar."
          : problemFrom(reason).message,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className={embedded ? "card stack" : "page page-narrow"}>
      {!embedded ? (
        <PageHeader
          title="Detalle de actividad"
          eyebrow="Actividades"
          description="Laps, datos disponibles y vínculo ajustable."
        />
      ) : (
        <h2>Detalle de actividad</h2>
      )}
      {error ? <ErrorState message={error} retry={load} /> : null}
      {detail ? (
        <>
          <p>
            {sports[detail.sport_type]} · {detail.local_date} ·{" "}
            {detail.timezone} · {detail.provider}
          </p>
          <p>
            {measured(detail.duration_sec, "s")} ·{" "}
            {measured(detail.distance_m, "m")} · {detail.telemetry_points}{" "}
            puntos recibidos
          </p>
          <label className="field">
            Sesión publicada
            <select
              className="select"
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
            >
              <option value="">Sin vínculo</option>
              {detail.prescribed_workout_id &&
              !workouts.some((w) => w.id === detail.prescribed_workout_id) ? (
                <option value={detail.prescribed_workout_id}>
                  Vínculo actual fuera de la semana
                </option>
              ) : null}
              {workouts
                .filter(
                  (w) =>
                    w.status === "published" &&
                    w.sport_type === detail.sport_type,
                )
                .map((workout) => (
                  <option key={workout.id} value={workout.id}>
                    {workout.title} · {workout.scheduled_date.slice(0, 10)}
                  </option>
                ))}
            </select>
          </label>
          <button
            className="button button-primary"
            disabled={busy}
            onClick={link}
          >
            Guardar vínculo · v{detail.version}
          </button>
          {message ? <p role="status">{message}</p> : null}
          <h3>Laps recibidos</h3>
          {detail.laps.length ? (
            detail.laps.map((lap) => (
              <p key={lap.index}>
                Lap {lap.index + 1}: {measured(lap.duration_sec, "s")} ·{" "}
                {measured(lap.distance_m, "m")} · FC{" "}
                {measured(lap.avg_heart_rate, "bpm")} · potencia{" "}
                {measured(lap.avg_power, "W")}
              </p>
            ))
          ) : (
            <p>Este archivo no contiene laps utilizables.</p>
          )}
        </>
      ) : (
        <p role="status">Cargando actividad…</p>
      )}
    </div>
  );
}
