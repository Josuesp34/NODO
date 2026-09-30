"use client";
import type {
  Sport,
  StepGroup,
  StepTarget,
  WorkoutInput,
  WorkoutStep,
} from "@/lib/contracts";
import { dateAtZone, dayInZone, isoDay } from "@/lib/dates";
export const sportNames: Record<Sport, string> = {
  running: "Carrera",
  cycling: "Ciclismo",
  swimming: "Natación",
  triathlon: "Triatlón",
};
export const weekNames = [
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
  "Domingo",
];
export function blankWorkout(timezone: string): WorkoutInput {
  return {
    title: "",
    description: null,
    sport_type: "running",
    scheduled_date: dateAtZone(isoDay(), timezone),
    block_id: null,
    steps: [{ repetitions: 1, steps: [{ kind: "work", duration_sec: 1800 }] }],
  };
}
export function WeekdayPicker({
  value,
  onChange,
}: {
  value: number[];
  onChange: (value: number[]) => void;
}) {
  return (
    <fieldset className="field">
      <legend>Días disponibles</legend>
      <div className="cluster">
        {weekNames.map((name, index) => (
          <label className="cluster" key={name}>
            <input
              type="checkbox"
              checked={value.includes(index)}
              onChange={() =>
                onChange(
                  value.includes(index)
                    ? value.filter((day) => day !== index)
                    : [...value, index].sort(),
                )
              }
            />
            {name}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
export function WorkoutFields({
  value,
  onChange,
  timezone,
}: {
  value: WorkoutInput;
  onChange: (value: WorkoutInput) => void;
  timezone: string;
}) {
  const patch = (change: Partial<WorkoutInput>) =>
    onChange({ ...value, ...change });
  function group(index: number, change: Partial<StepGroup>) {
    patch({
      steps: value.steps.map((item, position) =>
        position === index ? { ...item, ...change } : item,
      ),
    });
  }
  function step(gi: number, si: number, change: WorkoutStep) {
    group(gi, {
      steps: value.steps[gi].steps.map((item, index) =>
        index === si ? change : item,
      ),
    });
  }
  const unitFor = (metric: StepTarget["metric"]): StepTarget["unit"] =>
    metric === "pace"
      ? value.sport_type === "swimming"
        ? "sec_per_100m"
        : "sec_per_km"
      : metric === "power"
        ? "watts"
        : metric === "heart_rate"
          ? "bpm"
          : "rpe_0_10";
  return (
    <div className="stack">
      <div className="form-grid">
        <label className="field">
          Título
          <input
            className="input"
            value={value.title}
            onChange={(event) => patch({ title: event.target.value })}
            required
            maxLength={255}
          />
        </label>
        <label className="field">
          Deporte
          <select
            className="select"
            value={value.sport_type}
            onChange={(event) =>
              patch({ sport_type: event.target.value as Sport })
            }
          >
            {Object.entries(sportNames).map(([key, name]) => (
              <option key={key} value={key}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Fecha · {timezone}
          <input
            className="input"
            type="date"
            value={dayInZone(value.scheduled_date, timezone)}
            onChange={(event) =>
              event.target.value &&
              patch({
                scheduled_date: dateAtZone(event.target.value, timezone),
              })
            }
            required
          />
        </label>
        <label className="field span-all">
          Intención / nota
          <textarea
            className="textarea"
            value={value.description ?? ""}
            onChange={(event) =>
              patch({ description: event.target.value || null })
            }
            maxLength={4000}
          />
        </label>
      </div>
      {value.steps.map((item, gi) => (
        <fieldset className="card stack" key={gi}>
          <legend>Grupo {gi + 1}</legend>
          <label className="field">
            Repeticiones
            <input
              className="input"
              type="number"
              min={1}
              max={100}
              value={item.repetitions}
              onChange={(event) =>
                group(gi, { repetitions: Number(event.target.value) })
              }
              required
            />
          </label>
          {item.steps.map((current, si) => (
            <div className="stack" key={si}>
              <div className="form-grid">
                <label className="field">
                  Paso {si + 1}
                  <select
                    className="select"
                    value={current.kind}
                    onChange={(event) =>
                      step(gi, si, {
                        ...current,
                        kind: event.target.value as WorkoutStep["kind"],
                      })
                    }
                  >
                    <option value="warmup">Calentamiento</option>
                    <option value="work">Trabajo</option>
                    <option value="recovery">Recuperación</option>
                    <option value="cooldown">Vuelta a la calma</option>
                  </select>
                </label>
                <label className="field">
                  Medida
                  <select
                    className="select"
                    value={
                      current.distance_m !== undefined
                        ? "distance_m"
                        : "duration_sec"
                    }
                    onChange={(event) =>
                      step(gi, si, {
                        kind: current.kind,
                        target: current.target,
                        [event.target.value]:
                          current.distance_m ?? current.duration_sec ?? 1,
                      })
                    }
                  >
                    <option value="duration_sec">Duración · segundos</option>
                    <option value="distance_m">Distancia · metros</option>
                  </select>
                </label>
                <label className="field">
                  Cantidad
                  <input
                    className="input"
                    type="number"
                    min={0.01}
                    step="any"
                    value={current.distance_m ?? current.duration_sec ?? ""}
                    onChange={(event) =>
                      step(gi, si, {
                        ...current,
                        [current.distance_m !== undefined
                          ? "distance_m"
                          : "duration_sec"]: Number(event.target.value),
                      })
                    }
                    required
                  />
                </label>
              </div>
              <label className="cluster">
                <input
                  type="checkbox"
                  checked={Boolean(current.target)}
                  onChange={(event) =>
                    step(gi, si, {
                      ...current,
                      target: event.target.checked
                        ? {
                            metric: "rpe",
                            unit: "rpe_0_10",
                            minimum: 3,
                            maximum: 5,
                          }
                        : undefined,
                    })
                  }
                />
                Objetivo
              </label>
              {current.target ? (
                <div className="form-grid">
                  <label className="field">
                    Métrica
                    <select
                      className="select"
                      value={current.target.metric}
                      onChange={(event) => {
                        const metric = event.target
                          .value as StepTarget["metric"];
                        step(gi, si, {
                          ...current,
                          target: {
                            ...current.target!,
                            metric,
                            unit: unitFor(metric),
                          },
                        });
                      }}
                    >
                      <option value="rpe">RPE</option>
                      <option value="heart_rate">FC · bpm</option>
                      <option value="power">Potencia · W</option>
                      {value.sport_type === "running" ||
                      value.sport_type === "swimming" ? (
                        <option value="pace">Ritmo</option>
                      ) : null}
                    </select>
                  </label>
                  <label className="field">
                    Mínimo · {current.target.unit}
                    <input
                      className="input"
                      type="number"
                      min={0.01}
                      step="any"
                      value={current.target.minimum}
                      onChange={(event) =>
                        step(gi, si, {
                          ...current,
                          target: {
                            ...current.target!,
                            minimum: Number(event.target.value),
                          },
                        })
                      }
                      required
                    />
                  </label>
                  <label className="field">
                    Máximo · {current.target.unit}
                    <input
                      className="input"
                      type="number"
                      min={0.01}
                      step="any"
                      value={current.target.maximum}
                      onChange={(event) =>
                        step(gi, si, {
                          ...current,
                          target: {
                            ...current.target!,
                            maximum: Number(event.target.value),
                          },
                        })
                      }
                      required
                    />
                  </label>
                </div>
              ) : null}
              <button
                className="button button-danger"
                type="button"
                disabled={item.steps.length === 1}
                onClick={() =>
                  group(gi, { steps: item.steps.filter((_, i) => i !== si) })
                }
              >
                Eliminar paso {si + 1}
              </button>
            </div>
          ))}
          <div className="cluster">
            <button
              className="button"
              type="button"
              disabled={item.steps.length >= 20}
              onClick={() =>
                group(gi, {
                  steps: [...item.steps, { kind: "work", duration_sec: 300 }],
                })
              }
            >
              Añadir paso
            </button>
            <button
              className="button button-danger"
              type="button"
              disabled={value.steps.length === 1}
              onClick={() =>
                patch({ steps: value.steps.filter((_, i) => i !== gi) })
              }
            >
              Eliminar grupo
            </button>
          </div>
        </fieldset>
      ))}
      <button
        className="button"
        type="button"
        disabled={value.steps.length >= 50}
        onClick={() =>
          patch({
            steps: [
              ...value.steps,
              { repetitions: 1, steps: [{ kind: "work", duration_sec: 300 }] },
            ],
          })
        }
      >
        Añadir grupo
      </button>
    </div>
  );
}
