"use client";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { nodoRequest, problemFrom } from "@/lib/api";
import type { Athlete, Sport, WorkoutInput } from "@/lib/contracts";
import { useSession } from "./product-shell";
import { EmptyState, ErrorState, PageHeader, StatusBadge } from "./ui";
import {
  blankWorkout,
  sportNames,
  WeekdayPicker,
  WorkoutFields,
} from "./workout-fields";
type Group = { id: number; name: string };
type Member = {
  athlete_id: number;
  version: number;
  overrides: Record<string, unknown>;
};
type Template = {
  id: number;
  name: string;
  sport_type: Sport;
  version: number;
  workouts: (WorkoutInput & { key: string })[];
};
export function GroupsWorkspace() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [athletes, setAthletes] = useState<Athlete[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [name, setName] = useState("");
  const [athleteId, setAthleteId] = useState("");
  const [days, setDays] = useState([0, 1, 2, 3, 4, 5, 6]);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Member | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    void Promise.all([
      nodoRequest<Group[]>("groups"),
      nodoRequest<Athlete[]>("auth/athletes"),
    ])
      .then(([g, a]) => {
        setGroups(g);
        setAthletes(a);
      })
      .catch((r) => setError(problemFrom(r).message));
  }, []);
  function loadMembers() {
    if (selected !== null)
      void nodoRequest<Member[]>(`groups/${selected}/members`)
        .then(setMembers)
        .catch((r) => setError(problemFrom(r).message));
  }
  useEffect(() => {
    setEditing(null);
    setAthleteId("");
    loadMembers();
  }, [selected]);
  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const g = await nodoRequest<Group>("groups", {
        method: "POST",
        body: { name },
      });
      setGroups([...groups, g]);
      setSelected(g.id);
      setName("");
    } catch (r) {
      setError(problemFrom(r).message);
    } finally {
      setBusy(false);
    }
  }
  async function saveMember(e: FormEvent) {
    e.preventDefault();
    if (selected === null) return;
    setBusy(true);
    setError(null);
    try {
      const overrides = {
        ...(editing?.overrides ?? {}),
        available_weekdays: days,
      };
      await nodoRequest(
        `groups/${selected}/members${editing ? `/${editing.athlete_id}` : ""}`,
        {
          method: editing ? "PUT" : "POST",
          body: editing
            ? { overrides, expected_version: editing.version }
            : { athlete_id: Number(athleteId), overrides },
        },
      );
      loadMembers();
      setEditing(null);
      setAthleteId("");
    } catch (r) {
      setError(problemFrom(r).message);
    } finally {
      setBusy(false);
    }
  }
  async function remove(m: Member) {
    setError(null);
    try {
      await nodoRequest(
        `groups/${selected}/members/${m.athlete_id}?expected_version=${m.version}`,
        { method: "DELETE" },
      );
      loadMembers();
    } catch (r) {
      setError(problemFrom(r).message);
    }
  }
  const athleteName = (id: number) => {
    const a = athletes.find((x) => x.id === id);
    return a ? `${a.first_name} ${a.last_name}` : "Asignación no disponible";
  };
  return (
    <div className="page">
      <PageHeader
        title="Grupos"
        eyebrow="NODO Lab / Grupos"
        description="Cada atleta conserva sus días disponibles y excepciones. Aplicar una plantilla respeta las sesiones publicadas y editadas individualmente."
        actions={
          <Link className="button" href="/coach/templates">
            Aplicar plantilla
          </Link>
        }
      />
      {error ? <ErrorState message={error} retry={loadMembers} /> : null}
      <div className="split">
        <section className="stack">
          <label className="field">
            Grupo
            <select
              className="select"
              value={selected ?? ""}
              onChange={(e) =>
                setSelected(e.target.value ? Number(e.target.value) : null)
              }
            >
              <option value="">Selecciona un grupo</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </label>
          {selected !== null ? (
            members.length ? (
              members.map((m) => (
                <article className="card stack" key={m.athlete_id}>
                  <h2>{athleteName(m.athlete_id)}</h2>
                  <StatusBadge>Excepción v{m.version}</StatusBadge>
                  <p>
                    {
                      (Array.isArray(m.overrides.available_weekdays)
                        ? m.overrides.available_weekdays
                        : [0, 1, 2, 3, 4, 5, 6]
                      ).length
                    }{" "}
                    días disponibles
                  </p>
                  <div className="cluster">
                    <button
                      className="button"
                      onClick={() => {
                        setEditing(m);
                        setAthleteId(String(m.athlete_id));
                        setDays(
                          Array.isArray(m.overrides.available_weekdays)
                            ? (m.overrides.available_weekdays as number[])
                            : [0, 1, 2, 3, 4, 5, 6],
                        );
                      }}
                    >
                      Editar disponibilidad
                    </button>
                    <button
                      className="button button-danger"
                      onClick={() => void remove(m)}
                    >
                      Retirar del grupo
                    </button>
                  </div>
                </article>
              ))
            ) : (
              <EmptyState
                title="Grupo sin miembros."
                copy="Selecciona atletas de tu equipo para agregarlos."
              />
            )
          ) : null}
        </section>
        <section className="stack">
          <form className="card stack" onSubmit={create}>
            <h2>Nuevo grupo</h2>
            <label className="field">
              Nombre
              <input
                className="input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                maxLength={255}
              />
            </label>
            <button className="button" disabled={busy}>
              Crear grupo
            </button>
          </form>
          {selected !== null ? (
            <form className="card stack" onSubmit={saveMember}>
              <h2>{editing ? "Excepción individual" : "Agregar atleta"}</h2>
              <label className="field">
                Atleta
                <select
                  className="select"
                  value={athleteId}
                  onChange={(e) => setAthleteId(e.target.value)}
                  required
                  disabled={Boolean(editing)}
                >
                  <option value="">Selecciona atleta</option>
                  {athletes
                    .filter(
                      (a) =>
                        editing?.athlete_id === a.id ||
                        !members.some((m) => m.athlete_id === a.id),
                    )
                    .map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.first_name} {a.last_name}
                      </option>
                    ))}
                </select>
              </label>
              <WeekdayPicker value={days} onChange={setDays} />
              <p className="helper">
                Las sesiones fuera de disponibilidad se omiten y se muestran
                para revisión; no se desplazan automáticamente.
              </p>
              <button
                className="button button-primary"
                disabled={busy || !athleteId}
              >
                Guardar excepción
              </button>
              {editing ? (
                <button
                  type="button"
                  className="button"
                  onClick={() => {
                    setEditing(null);
                    setAthleteId("");
                  }}
                >
                  Cancelar edición
                </button>
              ) : null}
            </form>
          ) : null}
        </section>
      </div>
    </div>
  );
}

export function TemplatesWorkspace() {
  const { identity } = useSession();
  const zone = identity.timezone;
  const [items, setItems] = useState<Template[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [athletes, setAthletes] = useState<Athlete[]>([]);
  const [editing, setEditing] = useState<Template | null>(null);
  const [name, setName] = useState("");
  const [sport, setSport] = useState<Sport>("running");
  const [sessions, setSessions] = useState<(WorkoutInput & { key: string })[]>([
    { ...blankWorkout(zone), key: "session-1" },
  ]);
  const [templateId, setTemplateId] = useState("");
  const [groupId, setGroupId] = useState("");
  const [chosen, setChosen] = useState<number[]>([]);
  const [exceptionAthlete, setExceptionAthlete] = useState("");
  const [exceptionKey, setExceptionKey] = useState("");
  const [exceptionWorkout, setExceptionWorkout] = useState<WorkoutInput | null>(
    null,
  );
  const [overrides, setOverrides] = useState<
    Record<number, Record<string, unknown>>
  >({});
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  function load() {
    void Promise.all([
      nodoRequest<Template[]>("templates"),
      nodoRequest<Group[]>("groups"),
      nodoRequest<Athlete[]>("auth/athletes"),
    ])
      .then(([t, g, a]) => {
        setItems(t);
        setGroups(g);
        setAthletes(a);
      })
      .catch((r) => setError(problemFrom(r).message));
  }
  useEffect(load, []);
  const selected = items.find((t) => String(t.id) === templateId);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = {
        name,
        sport_type: sport,
        workouts: sessions,
        ...(editing ? { expected_version: editing.version } : {}),
      };
      const saved = await nodoRequest<Template>(
        editing ? `templates/${editing.id}` : "templates",
        { method: editing ? "PUT" : "POST", body },
      );
      setItems([...items.filter((t) => t.id !== saved.id), saved]);
      setEditing(saved);
      setResult(`Plantilla guardada · v${saved.version}`);
    } catch (r) {
      setError(problemFrom(r).message);
    } finally {
      setBusy(false);
    }
  }
  async function apply(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const applied = await nodoRequest<{
        workout_ids: number[];
        skipped: { athlete_id: number; key: string; reason: string }[];
      }>(`templates/${selected.id}/apply`, {
        method: "POST",
        body: {
          athlete_ids: chosen,
          group_id: groupId ? Number(groupId) : null,
          expected_version: selected.version,
          overrides,
        },
      });
      const reasons: Record<string, string> = {
        unavailable_day: "día no disponible",
        published_or_individually_edited:
          "sesión publicada o con edición individual",
      };
      setResult(
        `${applied.workout_ids.length} borradores creados o actualizados. ${applied.skipped.map((s) => `${athletes.find((a) => a.id === s.athlete_id)?.first_name ?? "Atleta"}: ${s.key} (${reasons[s.reason] ?? s.reason})`).join("; ") || "Sin omisiones."}`,
      );
    } catch (r) {
      setError(problemFrom(r).message);
    } finally {
      setBusy(false);
    }
  }
  function edit(t: Template) {
    setEditing(t);
    setName(t.name);
    setSport(t.sport_type);
    setSessions(t.workouts);
    setError(null);
  }
  function exception(k: string) {
    setExceptionKey(k);
    const raw = selected?.workouts.find((w) => w.key === k);
    setExceptionWorkout(raw ? { ...raw } : null);
  }
  return (
    <div className="page">
      <PageHeader
        title="Plantillas"
        eyebrow="NODO Lab / Plan"
        description="Versiona sesiones estructuradas. Reaplicar actualiza los borradores originales y conserva lo publicado y las ediciones individuales."
      />
      {error ? <ErrorState message={error} retry={load} /> : null}
      {result ? (
        <div className="alert alert-info" role="status">
          {result}
        </div>
      ) : null}
      <div className="stack">
        <section className="card stack">
          <h2>Plantillas guardadas</h2>
          {items.length ? (
            items.map((t) => (
              <div className="cluster" key={t.id}>
                <strong>{t.name}</strong>
                <StatusBadge>
                  v{t.version} · {t.workouts.length} sesiones
                </StatusBadge>
                <button className="button" onClick={() => edit(t)}>
                  Editar
                </button>
                <button
                  className="button"
                  onClick={() => {
                    setTemplateId(String(t.id));
                    setOverrides({});
                  }}
                >
                  Seleccionar para aplicar
                </button>
              </div>
            ))
          ) : (
            <p>No hay plantillas guardadas.</p>
          )}
        </section>
        <form className="card stack" onSubmit={save}>
          <h2>
            {editing
              ? `Editar ${editing.name} · v${editing.version}`
              : "Nueva plantilla"}
          </h2>
          <label className="field">
            Nombre
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={255}
            />
          </label>
          <label className="field">
            Disciplina base
            <select
              className="select"
              value={sport}
              onChange={(e) => setSport(e.target.value as Sport)}
            >
              {Object.entries(sportNames).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          {sessions.map((session, index) => (
            <section className="stack" key={session.key}>
              <h3>Sesión {index + 1}</h3>
              <WorkoutFields
                timezone={zone}
                value={session}
                onChange={(value) =>
                  setSessions(
                    sessions.map((w, i) =>
                      i === index ? { ...value, key: w.key } : w,
                    ),
                  )
                }
              />
              <button
                className="button button-danger"
                type="button"
                disabled={sessions.length === 1 || Boolean(editing)}
                onClick={() =>
                  setSessions(sessions.filter((_, i) => i !== index))
                }
              >
                Quitar sesión
              </button>
            </section>
          ))}
          <button
            className="button"
            type="button"
            disabled={sessions.length >= 100}
            onClick={() =>
              setSessions([
                ...sessions,
                {
                  ...blankWorkout(zone),
                  sport_type: sport,
                  key: `session-${Date.now()}`,
                },
              ])
            }
          >
            Añadir sesión
          </button>
          <div className="cluster">
            <button className="button button-primary" disabled={busy}>
              Guardar {editing ? "nueva versión" : "plantilla"}
            </button>
            {editing ? (
              <button
                className="button"
                type="button"
                onClick={() => {
                  setEditing(null);
                  setName("");
                  setSessions([{ ...blankWorkout(zone), key: "session-1" }]);
                }}
              >
                Nueva plantilla
              </button>
            ) : null}
          </div>
        </form>
        <form className="card stack" onSubmit={apply}>
          <h2>Aplicar como borrador</h2>
          <label className="field">
            Plantilla
            <select
              className="select"
              value={templateId}
              onChange={(e) => {
                setTemplateId(e.target.value);
                setOverrides({});
                setExceptionWorkout(null);
              }}
              required
            >
              <option value="">Selecciona plantilla</option>
              {items.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} · v{t.version}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Grupo opcional
            <select
              className="select"
              value={groupId}
              onChange={(e) => setGroupId(e.target.value)}
            >
              <option value="">Sin grupo</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </label>
          <fieldset>
            <legend>Atletas individuales</legend>
            {athletes.map((a) => (
              <label className="cluster" key={a.id}>
                <input
                  type="checkbox"
                  checked={chosen.includes(a.id)}
                  onChange={() =>
                    setChosen(
                      chosen.includes(a.id)
                        ? chosen.filter((id) => id !== a.id)
                        : [...chosen, a.id],
                    )
                  }
                />
                {a.first_name} {a.last_name}
              </label>
            ))}
          </fieldset>
          {selected ? (
            <>
              <h3>Excepción por atleta y sesión</h3>
              <label className="field">
                Atleta
                <select
                  className="select"
                  value={exceptionAthlete}
                  onChange={(e) => setExceptionAthlete(e.target.value)}
                >
                  <option value="">Sin excepción nueva</option>
                  {athletes.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.first_name} {a.last_name}
                    </option>
                  ))}
                </select>
              </label>
              {exceptionAthlete ? (
                <>
                  <WeekdayPicker
                    value={
                      (overrides[Number(exceptionAthlete)]
                        ?.available_weekdays as number[]) ?? [
                        0, 1, 2, 3, 4, 5, 6,
                      ]
                    }
                    onChange={(days) =>
                      setOverrides({
                        ...overrides,
                        [Number(exceptionAthlete)]: {
                          ...overrides[Number(exceptionAthlete)],
                          available_weekdays: days,
                        },
                      })
                    }
                  />
                  <label className="field">
                    Sesión a ajustar
                    <select
                      className="select"
                      value={exceptionKey}
                      onChange={(e) => exception(e.target.value)}
                    >
                      <option value="">Sólo disponibilidad</option>
                      {selected.workouts.map((w) => (
                        <option key={w.key} value={w.key}>
                          {w.title}
                        </option>
                      ))}
                    </select>
                  </label>
                  {exceptionWorkout ? (
                    <>
                      <WorkoutFields
                        timezone={
                          athletes.find(
                            (a) => String(a.id) === exceptionAthlete,
                          )?.timezone ?? zone
                        }
                        value={exceptionWorkout}
                        onChange={setExceptionWorkout}
                      />
                      <button
                        className="button"
                        type="button"
                        onClick={() => {
                          setOverrides({
                            ...overrides,
                            [Number(exceptionAthlete)]: {
                              ...overrides[Number(exceptionAthlete)],
                              [exceptionKey]: exceptionWorkout,
                            },
                          });
                          setResult(
                            "Excepción preparada. Usa Aplicar para guardarla.",
                          );
                        }}
                      >
                        Preparar excepción de sesión
                      </button>
                    </>
                  ) : null}
                </>
              ) : null}
            </>
          ) : null}
          <p className="helper">
            No publica sesiones. Una segunda aplicación idéntica no crea
            duplicados.
          </p>
          <button
            className="button button-primary"
            disabled={busy || !selected || (!groupId && !chosen.length)}
          >
            Aplicar en servidor
          </button>
        </form>
      </div>
    </div>
  );
}
