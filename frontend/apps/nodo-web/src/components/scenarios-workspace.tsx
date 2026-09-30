"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { nodoRequest, problemFrom } from "@/lib/api";
import { addDays, formatDay } from "@/lib/dates";
import { ErrorState, PageHeader, StatusBadge } from "./ui";

type Competition = {
  id: number;
  version: number;
  name: string;
  competition_date: string;
  discipline: string;
};
type Baseline = {
  ctl: number;
  atl: number;
  source: string;
  explanation: string;
  local_date: string;
  load_unit: string;
};
type ScenarioResult = {
  status: string;
  timezone: string;
  load_unit: string;
  initial_state: Baseline | null;
  review_note: string | null;
  alternatives: {
    name: string;
    total_assumed_load: number;
    competition_day_start_tsb: number | null;
    assumptions: string[];
    initial_state: Baseline | null;
    days: {
      local_date: string;
      load: number;
      ctl: number | null;
      atl: number | null;
      tsb: number | null;
    }[];
  }[];
};
const amount = (value: number | null) =>
  value == null
    ? "Sin estado inicial"
    : value.toLocaleString("es-MX", { maximumFractionDigits: 2 });

export function ScenariosWorkspace({ athleteId }: { athleteId: number }) {
  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [selected, setSelected] = useState("");
  const [start, setStart] = useState("");
  const [unit, setUnit] = useState("trimp");
  const [names, setNames] = useState(["Alternativa A", "Alternativa B"]);
  const [loads, setLoads] = useState<Record<string, string>[]>([{}, {}]);
  const [fill, setFill] = useState(["", ""]);
  const [explicit, setExplicit] = useState(false);
  const [initial, setInitial] = useState({ ctl: "", atl: "", explanation: "" });
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const listRequest = useRef<AbortController | null>(null);
  const comparisonRequest = useRef<AbortController | null>(null);
  function invalidate() {
    comparisonRequest.current?.abort();
    setResult(null);
    setBusy(false);
  }
  function load() {
    listRequest.current?.abort();
    const controller = new AbortController();
    listRequest.current = controller;
    invalidate();
    setCompetitions([]);
    setSelected("");
    setError(null);
    void nodoRequest<Competition[]>(`athletes/${athleteId}/competitions`, {
      signal: controller.signal,
    })
      .then((items) => {
        if (!controller.signal.aborted) setCompetitions(items);
      })
      .catch((reason) => {
        if (!controller.signal.aborted) setError(problemFrom(reason).message);
      });
  }
  useEffect(() => {
    load();
    return () => {
      listRequest.current?.abort();
      comparisonRequest.current?.abort();
    };
  }, [athleteId]);
  const competition = competitions.find((item) => String(item.id) === selected);
  const days = useMemo(() => {
    if (!start || !competition) return [];
    const count =
      Math.round(
        (Date.parse(`${competition.competition_date}T00:00:00Z`) -
          Date.parse(`${start}T00:00:00Z`)) /
          86400000,
      ) + 1;
    return count > 0 && count <= 42
      ? Array.from({ length: count }, (_, index) => addDays(start, index))
      : [];
  }, [start, competition]);
  async function compare(event: FormEvent) {
    event.preventDefault();
    comparisonRequest.current?.abort();
    const controller = new AbortController();
    comparisonRequest.current = controller;
    setBusy(true);
    setError(null);
    setResult(null);
    if (!competition) {
      setBusy(false);
      return;
    }
    try {
      const response = await nodoRequest<ScenarioResult>(
        `athletes/${athleteId}/competitions/${competition.id}/scenarios`,
        {
          method: "POST",
          signal: controller.signal,
          body: {
            expected_competition_version: competition.version,
            start_date: start,
            load_unit: unit,
            initial_state: explicit
              ? {
                  ctl: Number(initial.ctl),
                  atl: Number(initial.atl),
                  explanation: initial.explanation,
                }
              : null,
            alternatives: names.map((name, index) => ({
              name,
              daily_loads: days.map((day) => Number(loads[index][day])),
            })),
          },
        },
      );
      if (!controller.signal.aborted) setResult(response);
    } catch (reason) {
      if (controller.signal.aborted) return;
      const problem = problemFrom(reason);
      if (problem.status === 401 || problem.status === 403) setCompetitions([]);
      setError(
        problem.status === 409
          ? "La competencia cambió. Recarga y vuelve a comparar."
          : problem.message,
      );
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  const complete =
    days.length > 0 &&
    loads.every((alternative) =>
      days.every(
        (day) => alternative[day] !== undefined && alternative[day] !== "",
      ),
    );
  return (
    <div className="page">
      <PageHeader
        eyebrow="NODO Lab / Escenarios"
        title="Comparar cargas hasta una competencia"
        description="Introduce dos alternativas. El cálculo muestra supuestos matemáticos y conserva tu calendario."
        actions={
          <Link
            className="button"
            href={`/coach/athletes/${athleteId}/calendar`}
          >
            Volver al calendario
          </Link>
        }
      />
      {error ? <ErrorState message={error} retry={load} /> : null}
      {!competitions.length ? (
        <p className="card">
          Registra una competencia en el calendario para comparar alternativas.
        </p>
      ) : (
        <form className="stack" onSubmit={compare} onChange={invalidate}>
          <section className="card stack">
            <div className="form-grid">
              <label className="field">
                Competencia
                <select
                  className="select"
                  value={selected}
                  onChange={(event) => {
                    const item = competitions.find(
                      (entry) => String(entry.id) === event.target.value,
                    );
                    setSelected(event.target.value);
                    setStart(item ? addDays(item.competition_date, -13) : "");
                    setLoads([{}, {}]);
                    setFill(["", ""]);
                    setInitial({ ctl: "", atl: "", explanation: "" });
                    setResult(null);
                  }}
                  required
                >
                  <option value="">Selecciona una competencia</option>
                  {competitions.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} · {item.competition_date}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Primer día del escenario
                <input
                  className="input"
                  type="date"
                  value={start}
                  onChange={(event) => {
                    setStart(event.target.value);
                    setResult(null);
                  }}
                  max={competition?.competition_date}
                  required
                />
              </label>
              <label className="field">
                Unidad para todo el escenario
                <select
                  className="select"
                  value={unit}
                  onChange={(event) => {
                    setUnit(event.target.value);
                    setLoads([{}, {}]);
                    setFill(["", ""]);
                    setInitial({ ctl: "", atl: "", explanation: "" });
                    setResult(null);
                  }}
                >
                  <option value="trimp">TRIMP</option>
                  <option value="tss">TSS</option>
                </select>
              </label>
            </div>
            <p className="helper">
              Entre 1 y 42 días, incluyendo la fecha de competencia. Las cargas
              deben estar en una misma unidad; no se suman TRIMP y TSS.
            </p>
            <label className="cluster">
              <input
                type="checkbox"
                checked={explicit}
                onChange={(event) => setExplicit(event.target.checked)}
              />
              Introducir un estado inicial como supuesto
            </label>
            {explicit ? (
              <div className="form-grid">
                <label className="field">
                  CTL al cierre del día anterior
                  <input
                    className="input"
                    type="number"
                    min="0"
                    max="100000"
                    step="any"
                    value={initial.ctl}
                    onChange={(event) =>
                      setInitial({ ...initial, ctl: event.target.value })
                    }
                    required
                  />
                </label>
                <label className="field">
                  ATL al cierre del día anterior
                  <input
                    className="input"
                    type="number"
                    min="0"
                    max="100000"
                    step="any"
                    value={initial.atl}
                    onChange={(event) =>
                      setInitial({ ...initial, atl: event.target.value })
                    }
                    required
                  />
                </label>
                <label className="field span-all">
                  Fuente o explicación de este supuesto
                  <input
                    className="input"
                    value={initial.explanation}
                    onChange={(event) =>
                      setInitial({
                        ...initial,
                        explanation: event.target.value,
                      })
                    }
                    minLength={3}
                    maxLength={500}
                    required
                  />
                </label>
              </div>
            ) : (
              <p className="helper">
                Se usará el estado guardado del día anterior en esta unidad. Si
                falta, los promedios se mostrarán como datos insuficientes.
              </p>
            )}
          </section>
          {days.length ? (
            <div className="form-grid">
              {names.map((name, index) => (
                <section className="card stack" key={index}>
                  <label className="field">
                    Nombre de alternativa {index + 1}
                    <input
                      className="input"
                      value={name}
                      onChange={(event) =>
                        setNames(
                          names.map((entry, position) =>
                            position === index ? event.target.value : entry,
                          ),
                        )
                      }
                      required
                      maxLength={60}
                    />
                  </label>
                  <div className="cluster">
                    <label className="field">
                      Carga repetida cada día
                      <input
                        className="input"
                        type="number"
                        min="0"
                        max="100000"
                        step="any"
                        value={fill[index]}
                        onChange={(event) =>
                          setFill(
                            fill.map((entry, position) =>
                              position === index ? event.target.value : entry,
                            ),
                          )
                        }
                      />
                    </label>
                    <button
                      className="button"
                      type="button"
                      disabled={
                        fill[index] === "" ||
                        !Number.isFinite(Number(fill[index])) ||
                        Number(fill[index]) < 0
                      }
                      onClick={() => {
                        invalidate();
                        setLoads(
                          loads.map((entry, position) =>
                            position === index
                              ? Object.fromEntries(
                                  days.map((day) => [day, fill[index]]),
                                )
                              : entry,
                          ),
                        );
                      }}
                    >
                      Aplicar a estos días
                    </button>
                  </div>
                  <p className="helper">
                    Cero significa un descanso que tú estás suponiendo. Un campo
                    vacío no se convierte en cero.
                  </p>
                  {days.map((day) => (
                    <label className="field" key={day}>
                      {formatDay(day, { day: "numeric", month: "short" })} ·{" "}
                      {unit.toUpperCase()}
                      <input
                        className="input"
                        type="number"
                        min="0"
                        max="100000"
                        step="any"
                        value={loads[index][day] ?? ""}
                        onChange={(event) =>
                          setLoads(
                            loads.map((entry, position) =>
                              position === index
                                ? { ...entry, [day]: event.target.value }
                                : entry,
                            ),
                          )
                        }
                        required
                      />
                    </label>
                  ))}
                </section>
              ))}
            </div>
          ) : selected ? (
            <p role="status">
              Elige un período de hasta 42 días anterior a la competencia.
            </p>
          ) : null}
          <button
            className="button button-primary"
            disabled={!complete || busy}
          >
            {busy ? "Calculando…" : "Comparar alternativas"}
          </button>
        </form>
      )}
      {result ? (
        <section className="stack" style={{ marginTop: 24 }}>
          <h2>
            Comparación · {result.load_unit.toUpperCase()} · {result.timezone}
          </h2>
          {result.status === "insufficient_initial_state" ? (
            <p className="alert alert-info" role="status">
              Falta un estado inicial compatible para calcular CTL, ATL y TSB.
              Introduce un supuesto explicado o revisa los datos del día
              anterior.
            </p>
          ) : null}
          {result.review_note ? (
            <p className="alert alert-info" role="status">
              {result.review_note}
            </p>
          ) : null}
          {result.alternatives.map((alternative) => (
            <article className="card stack" key={alternative.name}>
              <h3>{alternative.name}</h3>
              <StatusBadge>Hipótesis de carga</StatusBadge>
              <p>
                Carga supuesta total: {amount(alternative.total_assumed_load)}{" "}
                {result.load_unit.toUpperCase()}. TSB al inicio del día de
                competencia: {amount(alternative.competition_day_start_tsb)}.
              </p>
              {alternative.initial_state ? (
                <p>
                  Estado inicial al {alternative.initial_state.local_date}: CTL{" "}
                  {amount(alternative.initial_state.ctl)}, ATL{" "}
                  {amount(alternative.initial_state.atl)}.{" "}
                  {alternative.initial_state.explanation}
                </p>
              ) : null}
              <ul>
                {alternative.assumptions.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <div style={{ overflowX: "auto" }}>
                <table>
                  <caption>
                    Promedios al cierre; TSB al inicio de cada día ·{" "}
                    {result.load_unit.toUpperCase()}
                  </caption>
                  <thead>
                    <tr>
                      <th>Día local</th>
                      <th>Carga supuesta</th>
                      <th>CTL</th>
                      <th>ATL</th>
                      <th>TSB</th>
                    </tr>
                  </thead>
                  <tbody>
                    {alternative.days.map((day) => (
                      <tr key={day.local_date}>
                        <td>{day.local_date}</td>
                        <td>{amount(day.load)}</td>
                        <td>{amount(day.ctl)}</td>
                        <td>{amount(day.atl)}</td>
                        <td>{amount(day.tsb)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          ))}
        </section>
      ) : null}
    </div>
  );
}
