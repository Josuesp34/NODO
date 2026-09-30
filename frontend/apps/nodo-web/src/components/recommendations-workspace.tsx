"use client";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { nodoRequest, problemFrom } from "@/lib/api";
import { addDays, isoDay } from "@/lib/dates";
import type { Athlete, Workout, WorkoutInput } from "@/lib/contracts";
import { ErrorState, PageHeader, StatusBadge } from "./ui";
import { WorkoutFields } from "./workout-fields";
type Proposal = {
  id: number;
  athlete_id: number;
  workout_id: number;
  base_plan_version: number;
  changes: Partial<WorkoutInput>;
  status: string;
  evidence: Record<string, unknown>[];
  rules_version: string;
  model_version: string;
};
const inputOf = (w: Workout): WorkoutInput => ({
  title: w.title,
  description: w.description,
  scheduled_date: w.scheduled_date,
  sport_type: w.sport_type,
  block_id: w.block_id,
  steps: w.steps,
});
export function ManualRecommendationsWorkspace() {
  const display = (key: string, value: unknown) => key === "steps" ? `${Array.isArray(value) ? value.length : 0} grupos: ${Array.isArray(value) ? value.map(g => `${g.repetitions} × ${g.steps.map((step: {duration_sec?: number;distance_m?: number}) => step.distance_m ? `${step.distance_m} m` : `${step.duration_sec} s`).join(" + ")}`).join("; ") : "sin dato"}` : String(value ?? "Sin dato");
  const [items, setItems] = useState<Proposal[]>([]);
  const [athletes, setAthletes] = useState<Athlete[]>([]);
  const [athleteId, setAthleteId] = useState("");
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [workoutId, setWorkoutId] = useState("");
  const [draft, setDraft] = useState<WorkoutInput | null>(null);
  const [modifying, setModifying] = useState<Proposal | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [since, setSince] = useState(addDays(isoDay(), -14));
  const [until, setUntil] = useState(addDays(isoDay(), 42));
  function load() {
    void Promise.all([
      nodoRequest<Proposal[]>("recommendations"),
      nodoRequest<Athlete[]>("auth/athletes"),
    ])
      .then(([p, a]) => {
        setItems(p);
        setAthletes(a);
      })
      .catch((r) => setError(problemFrom(r).message));
  }
  useEffect(load, []);
  function loadWorkouts() {
    if (athleteId)
      void nodoRequest<Workout[]>(
        `athletes/${athleteId}/workouts?start=${since}&end=${until}`,
      )
        .then(setWorkouts)
        .catch((r) => setError(problemFrom(r).message));
  }
  useEffect(() => {
    if (!modifying) {
      setDraft(null);
      setWorkoutId("");
    }
    loadWorkouts();
  }, [athleteId, since, until]);
  const athlete = athletes.find((a) => String(a.id) === athleteId);
  async function save(e: FormEvent) {
    e.preventDefault();
    if (!draft) return;
    setBusy(true);
    setError(null);
    try {
      if (modifying) {
        await nodoRequest(`recommendations/${modifying.id}/decision`, {
          method: "POST",
          body: {
            action: "modify",
            changes: draft,
            expected_plan_version: modifying.base_plan_version,
            note: note || null,
          },
        });
      } else {
        const base = workouts.find((w) => String(w.id) === workoutId);
        await nodoRequest("recommendations", {
          method: "POST",
          body: {
            athlete_id: Number(athleteId),
            workout_id: Number(workoutId),
            changes: draft,
            evidence: [
              {
                source: "coach_manual",
                note: note || "Ajuste manual revisado",
                base_version: base?.version,
              },
            ],
          },
        });
      }
      load();
      setDraft(null);
      setModifying(null);
      setNote("");
      loadWorkouts();
    } catch (r) {
      setError(
        problemFrom(r).status === 409
          ? "El plan o la propuesta cambió. Recarga la sesión y crea una propuesta con la versión vigente."
          : problemFrom(r).message,
      );
    } finally {
      setBusy(false);
    }
  }
  async function decide(p: Proposal, action: "approve" | "reject") {
    setBusy(true);
    setError(null);
    try {
      await nodoRequest(`recommendations/${p.id}/decision`, {
        method: "POST",
        body: {
          action,
          expected_plan_version: p.base_plan_version,
          note: note || null,
        },
      });
      load();
      loadWorkouts();
    } catch (r) {
      setError(problemFrom(r).message);
    } finally {
      setBusy(false);
    }
  }
  async function modify(p: Proposal) {
    setError(null);
    try {
      const related = await nodoRequest<Workout[]>(
        `athletes/${p.athlete_id}/workouts?start=${addDays(isoDay(), -180)}&end=${addDays(isoDay(), 180)}`,
      );
      const base = related.find((w) => w.id === p.workout_id);
      if (!base) {
        setError(
          "Sesión fuera del período. Abre su calendario para revisar la versión.",
        );
        return;
      }
      setAthleteId(String(p.athlete_id));
      setWorkouts(related);
      setWorkoutId(String(base.id));
      setModifying(p);
      setDraft({ ...inputOf(base), ...p.changes });
    } catch (r) {
      setError(problemFrom(r).message);
    }
  }
  return (
    <div className="page">
      <PageHeader
        title="Propuestas"
        eyebrow="NODO Lab / Decisiones"
        description="Revisa evidencia y cambios antes de aprobar, modificar o rechazar. Ninguna decisión publica automáticamente una sesión."
      />
      {error ? <ErrorState message={error} retry={load} /> : null}
      <div className="stack">
        <section className="stack">
          {items.length ? (
            items.map((p) => (
              <article className="card stack" key={p.id}>
                <div className="cluster">
                  <StatusBadge>{p.status}</StatusBadge>
                  <span>
                    Base v{p.base_plan_version} ·{" "}
                    {athletes.find((a) => a.id === p.athlete_id)?.first_name ??
                      "Atleta"}
                  </span>
                </div>
                <h2>{p.changes.title ?? "Ajuste de sesión"}</h2>
                <p className="helper">
                  Reglas {p.rules_version} · origen {p.model_version}
                </p>
                <dl>
                  {Object.entries(p.changes).map(([key, value]) => (
                    <div key={key}>
                      <dt>
                        {(
                          {
                            title: "Título propuesto",
                            description: "Nota propuesta",
                            scheduled_date: "Fecha propuesta",
                            sport_type: "Disciplina",
                            steps: "Estructura",
                            block_id: "Bloque",
                          } as Record<string, string>
                        )[key] ?? key}
                      </dt>
                      <dd>
                        <span>Antes: {display(key, (p.evidence.find(e => e.source === "plan_snapshot")?.snapshot as Record<string, unknown> | undefined)?.[key])}</span><br />
                        <span>Propuesta: {display(key, value)}</span>
                      </dd>
                    </div>
                  ))}
                </dl>
                <details>
                  <summary>Evidencia y contexto</summary>
                  {p.evidence.map((e, index) => (
                    <p key={index}>
                      {String(e.source ?? e.metric_type ?? "Contexto")} ·{" "}
                      {String(e.note ?? e.value ?? e.reason ?? "Sin detalle")}
                    </p>
                  ))}
                  {!p.evidence.length ? (
                    <p>
                      Sin evidencia adjunta. Revisa el contexto antes de
                      decidir.
                    </p>
                  ) : null}
                </details>
                <Link
                  className="button"
                  href={`/coach/athletes/${p.athlete_id}/calendar`}
                >
                  Revisar calendario
                </Link>
                {p.status === "pending" ? (
                  <div className="cluster">
                    <button
                      className="button button-primary"
                      disabled={busy}
                      onClick={() => void decide(p, "approve")}
                    >
                      Aprobar
                    </button>
                    <button
                      className="button"
                      disabled={busy}
                      onClick={() => void modify(p)}
                    >
                      Modificar y aprobar
                    </button>
                    <button
                      className="button button-danger"
                      disabled={busy}
                      onClick={() => void decide(p, "reject")}
                    >
                      Rechazar
                    </button>
                  </div>
                ) : null}
              </article>
            ))
          ) : (
            <p>No hay propuestas.</p>
          )}
        </section>
        <form className="card stack" onSubmit={save}>
          <h2>
            {modifying
              ? "Modificar propuesta antes de aprobar"
              : "Crear propuesta manual"}
          </h2>
          <label className="field">
            Atleta
            <select
              className="select"
              value={athleteId}
              onChange={(e) => {
                setModifying(null);
                setAthleteId(e.target.value);
              }}
              required
              disabled={Boolean(modifying)}
            >
              <option value="">Selecciona atleta</option>
              {athletes.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.first_name} {a.last_name}
                </option>
              ))}
            </select>
          </label>
          <div className="form-grid">
            <label className="field">
              Desde
              <input
                className="input"
                type="date"
                value={since}
                onChange={(e) => setSince(e.target.value)}
              />
            </label>
            <label className="field">
              Hasta
              <input
                className="input"
                type="date"
                value={until}
                onChange={(e) => setUntil(e.target.value)}
              />
            </label>
          </div>
          <label className="field">
            Sesión borrador
            <select
              className="select"
              value={workoutId}
              onChange={(e) => {
                setWorkoutId(e.target.value);
                const w = workouts.find((w) => String(w.id) === e.target.value);
                setDraft(w ? inputOf(w) : null);
              }}
              required
              disabled={Boolean(modifying)}
            >
              <option value="">Selecciona sesión</option>
              {workouts
                .filter((w) => w.status === "draft")
                .map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.title} · {w.scheduled_date.slice(0, 10)} · v{w.version}
                  </option>
                ))}
            </select>
          </label>
          {draft ? (
            <WorkoutFields
              value={draft}
              onChange={setDraft}
              timezone={athlete?.timezone ?? "UTC"}
            />
          ) : null}
          <label className="field">
            Razón de la propuesta / nota de decisión
            <textarea
              className="textarea"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={2000}
            />
          </label>
          <button className="button button-primary" disabled={busy || !draft}>
            {modifying ? "Guardar modificación y aprobar" : "Crear propuesta"}
          </button>
          {modifying ? (
            <button
              className="button"
              type="button"
              onClick={() => {
                setModifying(null);
                setDraft(null);
              }}
            >
              Cancelar modificación
            </button>
          ) : null}
        </form>
      </div>
    </div>
  );
}
