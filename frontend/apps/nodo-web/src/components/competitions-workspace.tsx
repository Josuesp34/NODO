"use client";
import { FormEvent, useEffect, useState } from "react";
import { nodoRequest, problemFrom } from "@/lib/api";
import type { Sport } from "@/lib/contracts";
import { isoDay } from "@/lib/dates";
import { ErrorState, StatusBadge } from "./ui";
import { sportNames } from "./workout-fields";
type Competition = {
  id: number;
  version: number;
  name: string;
  competition_date: string;
  discipline: Sport;
  priority: "A" | "B" | "C";
};
export function CompetitionsWorkspace({
  athleteId,
  editable = false,
}: {
  athleteId: number;
  editable?: boolean;
}) {
  const [items, setItems] = useState<Competition[]>([]);
  const [editing, setEditing] = useState<Competition | null>(null);
  const [form, setForm] = useState({
    name: "",
    competition_date: isoDay(),
    discipline: "running" as Sport,
    priority: "B" as "A" | "B" | "C",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  function load() {
    void nodoRequest<Competition[]>(`athletes/${athleteId}/competitions`)
      .then(setItems)
      .catch((r) => setError(problemFrom(r).message));
  }
  useEffect(load, [athleteId]);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await nodoRequest(
        `athletes/${athleteId}/competitions${editing ? `/${editing.id}` : ""}`,
        {
          method: editing ? "PUT" : "POST",
          body: {
            ...form,
            ...(editing ? { expected_version: editing.version } : {}),
          },
        },
      );
      load();
      setEditing(null);
      setForm({ ...form, name: "" });
    } catch (r) {
      setError(problemFrom(r).message);
    } finally {
      setBusy(false);
    }
  }
  async function remove(c: Competition) {
    setBusy(true);
    setError(null);
    try {
      await nodoRequest(
        `athletes/${athleteId}/competitions/${c.id}?expected_version=${c.version}`,
        { method: "DELETE" },
      );
      load();
    } catch (r) {
      setError(problemFrom(r).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card stack" style={{ marginTop: 18 }}>
      <h2>Competencias objetivo</h2>
      {error ? <ErrorState message={error} retry={load} /> : null}
      {items.map((c) => (
        <article className="stack" key={c.id}>
          <div className="cluster">
            <strong>{c.name}</strong>
            <StatusBadge>Prioridad {c.priority}</StatusBadge>
            <span>
              {c.competition_date} · {sportNames[c.discipline]}
            </span>
          </div>
          {editable ? (
            <div className="cluster">
              <button
                className="button"
                onClick={() => {
                  setEditing(c);
                  setForm({
                    name: c.name,
                    competition_date: c.competition_date,
                    discipline: c.discipline,
                    priority: c.priority,
                  });
                }}
              >
                Editar
              </button>
              <button
                className="button button-danger"
                disabled={busy}
                onClick={() => void remove(c)}
              >
                Eliminar
              </button>
            </div>
          ) : null}
        </article>
      ))}
      {!items.length ? (
        <p className="helper">Sin competencias registradas.</p>
      ) : null}
      {editable ? (
        <form className="stack" onSubmit={save}>
          <h3>{editing ? "Editar competencia" : "Nueva competencia"}</h3>
          <div className="form-grid">
            <label className="field">
              Nombre
              <input
                className="input"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                maxLength={255}
                required
              />
            </label>
            <label className="field">
              Fecha
              <input
                className="input"
                type="date"
                value={form.competition_date}
                onChange={(e) =>
                  setForm({ ...form, competition_date: e.target.value })
                }
                required
              />
            </label>
            <label className="field">
              Disciplina
              <select
                className="select"
                value={form.discipline}
                onChange={(e) =>
                  setForm({ ...form, discipline: e.target.value as Sport })
                }
              >
                {Object.entries(sportNames).map(([k, v]) => (
                  <option value={k} key={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Prioridad
              <select
                className="select"
                value={form.priority}
                onChange={(e) =>
                  setForm({
                    ...form,
                    priority: e.target.value as "A" | "B" | "C",
                  })
                }
              >
                {["A", "B", "C"].map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </label>
          </div>
          <button className="button button-primary" disabled={busy}>
            Guardar competencia
          </button>
          {editing ? (
            <button
              className="button"
              type="button"
              onClick={() => setEditing(null)}
            >
              Cancelar
            </button>
          ) : null}
        </form>
      ) : null}
    </section>
  );
}
