import type { Workout, WorkoutStep } from "@/lib/contracts";
import { formatDay } from "@/lib/dates";
import { StatusBadge } from "./ui";

function formatMeasure(step: WorkoutStep) {
  if (step.distance_m) return step.distance_m >= 1000 ? `${step.distance_m / 1000} km` : `${step.distance_m} m`;
  const seconds = step.duration_sec ?? 0;
  if (seconds >= 3600) return `${Math.floor(seconds / 3600)} h ${Math.round((seconds % 3600) / 60)} min`;
  if (seconds >= 60) return `${Math.floor(seconds / 60)} min ${seconds % 60 ? `${seconds % 60} s` : ""}`.trim();
  return `${seconds} s`;
}

function targetLabel(step: WorkoutStep) {
  if (!step.target) return null;
  return `${step.target.minimum}–${step.target.maximum} ${step.target.unit}`;
}

const kindLabel: Record<WorkoutStep["kind"], string> = { warmup: "Calentamiento", work: "Trabajo", recovery: "Recuperación", cooldown: "Vuelta a la calma" };

export function WorkoutView({ workout, compact = false }: { workout: Workout; compact?: boolean }) {
  return <article className="card today-card"><header className="today-top"><div><StatusBadge>{workout.sport_type}</StatusBadge><h2>{workout.title}</h2><p>{formatDay(workout.scheduled_date, { weekday: "long", day: "numeric", month: "long" })}</p></div><span className="badge">PUBLICADA · V{workout.version}</span></header>{workout.description ? <div style={{ padding: "20px 24px" }}><p className="muted">{workout.description}</p></div> : null}{!compact ? <div className="workout-steps">{workout.steps.map((group, groupIndex) => <section className="workout-group" key={groupIndex}><div className="cluster" style={{ justifyContent: "space-between" }}><strong>Grupo {groupIndex + 1}</strong><span className="badge badge-signal">{group.repetitions}×</span></div>{group.steps.map((step, stepIndex) => <div className="workout-step" key={stepIndex}><span className="step-number">{String(stepIndex + 1).padStart(2, "0")}</span><div><strong>{kindLabel[step.kind]}</strong>{targetLabel(step) ? <p className="helper">Objetivo · {targetLabel(step)}</p> : null}</div><span>{formatMeasure(step)}</span></div>)}</section>)}</div> : null}</article>;
}
