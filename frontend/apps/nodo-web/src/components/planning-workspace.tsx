"use client";

import Link from "next/link";
import { CompetitionsWorkspace } from "./competitions-workspace";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { nodoRequest, problemFrom } from "@/lib/api";
import { addDays, dateAtZone, dayInZone, formatDay, isoDay, monthRange } from "@/lib/dates";
import type { Athlete, Block, Sport, StepKind, TargetMetric, TargetUnit, Workout, WorkoutInput } from "@/lib/contracts";
import { EmptyState, ErrorState, PageHeader, SectionHeader, StatusBadge } from "./ui";

type StepDraft = { kind: StepKind; measure: "duration" | "distance"; amount: string; target: boolean; metric: TargetMetric; unit: TargetUnit; minimum: string; maximum: string };
type GroupDraft = { repetitions: string; steps: StepDraft[] };
type EditorDraft = { title: string; description: string; scheduled_date: string; sport_type: Sport; block_id: string; groups: GroupDraft[] };

const blankStep = (kind: StepKind = "work"): StepDraft => ({ kind, measure: "duration", amount: kind === "warmup" ? "900" : "", target: false, metric: "rpe", unit: "rpe_0_10", minimum: "", maximum: "" });
const blankGroup = (): GroupDraft => ({ repetitions: "1", steps: [blankStep("warmup"), blankStep("work")] });
const blankEditor = (day = isoDay()): EditorDraft => ({ title: "", description: "", scheduled_date: day, sport_type: "running", block_id: "", groups: [blankGroup()] });
const targetUnits: Record<TargetMetric, TargetUnit[]> = { pace: ["sec_per_km", "sec_per_100m"], power: ["watts"], heart_rate: ["bpm"], rpe: ["rpe_0_10"] };

function toDraft(workout: Workout, timezone: string): EditorDraft {
  return {
    title: workout.title,
    description: workout.description ?? "",
    scheduled_date: dayInZone(workout.scheduled_date, timezone),
    sport_type: workout.sport_type,
    block_id: workout.block_id ? String(workout.block_id) : "",
    groups: workout.steps.map((group) => ({ repetitions: String(group.repetitions), steps: group.steps.map((step) => ({ kind: step.kind, measure: step.distance_m ? "distance" : "duration", amount: String(step.distance_m ?? step.duration_sec ?? ""), target: Boolean(step.target), metric: step.target?.metric ?? "rpe", unit: step.target?.unit ?? "rpe_0_10", minimum: step.target ? String(step.target.minimum) : "", maximum: step.target ? String(step.target.maximum) : "" })) })),
  };
}

function buildInput(draft: EditorDraft, timezone: string): WorkoutInput {
  const groups = draft.groups.map((group) => ({
    repetitions: Number(group.repetitions),
    steps: group.steps.map((step) => ({
      kind: step.kind,
      ...(step.measure === "duration" ? { duration_sec: Number(step.amount) } : { distance_m: Number(step.amount) }),
      ...(step.target ? { target: { metric: step.metric, unit: step.unit, minimum: Number(step.minimum), maximum: Number(step.maximum) } } : {}),
    })),
  }));
  return { title: draft.title.trim(), description: draft.description.trim() || null, scheduled_date: dateAtZone(draft.scheduled_date, timezone), sport_type: draft.sport_type, block_id: draft.block_id ? Number(draft.block_id) : null, steps: groups };
}

function validate(draft: EditorDraft) {
  if (!draft.title.trim()) return "Escribe un título para la sesión.";
  if (!draft.groups.length) return "La sesión necesita al menos un grupo.";
  for (const [groupIndex, group] of draft.groups.entries()) {
    if (!Number.isInteger(Number(group.repetitions)) || Number(group.repetitions) < 1) return `Las repeticiones del grupo ${groupIndex + 1} no son válidas.`;
    if (!group.steps.length) return `El grupo ${groupIndex + 1} necesita al menos un paso.`;
    for (const [stepIndex, step] of group.steps.entries()) {
      if (!Number.isFinite(Number(step.amount)) || Number(step.amount) <= 0) return `Revisa la medida del paso ${stepIndex + 1} del grupo ${groupIndex + 1}.`;
      if (step.target && (!Number.isFinite(Number(step.minimum)) || !Number.isFinite(Number(step.maximum)) || Number(step.minimum) > Number(step.maximum))) return `El objetivo del paso ${stepIndex + 1} necesita un rango válido.`;
    }
  }
  return null;
}

export function PlanningWorkspace({ athleteId }: { athleteId: number }) {
  const [athlete, setAthlete] = useState<Athlete | null>(null);
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [anchor, setAnchor] = useState(isoDay());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editor, setEditor] = useState<EditorDraft | null>(null);
  const [editing, setEditing] = useState<Workout | null>(null);
  const [saving, setSaving] = useState(false);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [blockOpen, setBlockOpen] = useState(false);
  const [block, setBlock] = useState({ title: "", start_date: isoDay(), end_date: addDays(isoDay(), 28) });

  const range = useMemo(() => monthRange(anchor), [anchor]);
  function load() {
    setLoading(true); setError(null);
    void Promise.all([
      nodoRequest<Athlete[]>("auth/athletes"),
      nodoRequest<Block[]>(`athletes/${athleteId}/blocks`),
      nodoRequest<Workout[]>(`athletes/${athleteId}/workouts?start=${range.start}&end=${range.end}`),
    ]).then(([athletes, nextBlocks, nextWorkouts]) => { setAthlete(athletes.find((item) => item.id === athleteId) ?? null); setBlocks(nextBlocks); setWorkouts(nextWorkouts); }).catch((reason) => setError(problemFrom(reason).message)).finally(() => setLoading(false));
  }
  useEffect(load, [athleteId, range.end, range.start]);

  const calendarDays = useMemo(() => {
    const first = new Date(`${range.start}T12:00:00`);
    const start = addDays(range.start, -((first.getDay() + 6) % 7));
    return Array.from({ length: 42 }, (_, index) => addDays(start, index));
  }, [range.start]);
  const workoutsByDay = useMemo(() => workouts.reduce<Record<string, Workout[]>>((map, workout) => { const day = dayInZone(workout.scheduled_date, athlete?.timezone ?? "UTC"); (map[day] ??= []).push(workout); return map; }, {}), [workouts, athlete?.timezone]);

  function shiftMonth(offset: number) {
    const current = new Date(`${anchor}T12:00:00`);
    setAnchor(isoDay(new Date(current.getFullYear(), current.getMonth() + offset, 1)));
  }
  function openNew(day = isoDay()) { setEditing(null); setEditor(blankEditor(day)); setEditorError(null); setConflict(false); }
  function openExisting(workout: Workout) { setEditing(workout); setEditor(toDraft(workout, athlete?.timezone ?? "UTC")); setEditorError(null); setConflict(false); }
  function updateGroup(groupIndex: number, patch: Partial<GroupDraft>) { setEditor((current) => current ? { ...current, groups: current.groups.map((group, index) => index === groupIndex ? { ...group, ...patch } : group) } : current); }
  function updateStep(groupIndex: number, stepIndex: number, patch: Partial<StepDraft>) { setEditor((current) => current ? { ...current, groups: current.groups.map((group, index) => index === groupIndex ? { ...group, steps: group.steps.map((step, position) => position === stepIndex ? { ...step, ...patch } : step) } : group) } : current); }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!editor) return; const invalid = validate(editor); if (invalid) { setEditorError(invalid); return; }
    setSaving(true); setEditorError(null); setConflict(false);
    try {
      const input = buildInput(editor, athlete?.timezone ?? "UTC");
      const saved = editing
        ? await nodoRequest<Workout>(`athletes/${athleteId}/workouts/${editing.id}`, { method: "PUT", body: { ...input, expected_version: editing.version } })
        : await nodoRequest<Workout>(`athletes/${athleteId}/workouts`, { method: "POST", body: input });
      setWorkouts((current) => [...current.filter((item) => item.id !== saved.id), saved].sort((a, b) => a.scheduled_date.localeCompare(b.scheduled_date)));
      setEditing(saved); setEditor(toDraft(saved, athlete?.timezone ?? "UTC"));
    } catch (reason) { const problem = problemFrom(reason); if (problem.status === 409) setConflict(true); else setEditorError(problem.message); }
    finally { setSaving(false); }
  }

  async function publish() {
    if (!editing) return; setSaving(true); setEditorError(null); setConflict(false);
    try {
      const published = await nodoRequest<Workout>(`athletes/${athleteId}/workouts/${editing.id}/publish`, { method: "POST", body: { expected_version: editing.version } });
      setWorkouts((current) => current.map((item) => item.id === published.id ? published : item)); setEditing(published); setEditor(toDraft(published, athlete?.timezone ?? "UTC"));
    } catch (reason) { const problem = problemFrom(reason); if (problem.status === 409) setConflict(true); else setEditorError(problem.message); }
    finally { setSaving(false); }
  }

  async function createBlock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSaving(true); setEditorError(null);
    try { const created = await nodoRequest<Block>(`athletes/${athleteId}/blocks`, { method: "POST", body: block }); setBlocks((current) => [...current, created]); setBlockOpen(false); setBlock({ title: "", start_date: isoDay(), end_date: addDays(isoDay(), 28) }); }
    catch (reason) { setEditorError(problemFrom(reason).message); }
    finally { setSaving(false); }
  }

  if (error && !athlete) return <div className="page"><ErrorState message={error} retry={load} /></div>;
  return <div className="page"><PageHeader eyebrow="NODO Lab / Planificación" title={athlete ? `${athlete.first_name} ${athlete.last_name}` : "Calendario"} description={athlete ? `Plan en ${athlete.timezone}. Las fechas se presentan en la zona del atleta; la API conserva la autoridad final.` : "Cargando atleta…"} actions={<><Link className="button" href={`/coach/athletes/${athleteId}/activities`}>Actividades</Link><Link className="button" href={`/coach/athletes/${athleteId}/profile`}>Perfil</Link><button className="button" type="button" onClick={() => setBlockOpen((value) => !value)}>+ Bloque</button><button className="button button-primary" type="button" onClick={() => openNew()}>+ Sesión</button></>} />{editorError && !editor ? <ErrorState message={editorError} /> : null}{blockOpen ? <form className="card stack" onSubmit={createBlock}><div><StatusBadge tone="coral">Estructura</StatusBadge><h2>Nuevo bloque</h2></div><div className="form-grid"><label className="field"><span className="field-label">Nombre</span><input className="input" value={block.title} onChange={(event) => setBlock({ ...block, title: event.target.value })} required /></label><label className="field"><span className="field-label">Inicio</span><input className="input" type="date" value={block.start_date} onChange={(event) => setBlock({ ...block, start_date: event.target.value })} required /></label><label className="field"><span className="field-label">Fin</span><input className="input" type="date" value={block.end_date} onChange={(event) => setBlock({ ...block, end_date: event.target.value })} required /></label></div><button className="button button-primary" disabled={saving}>Guardar bloque</button></form> : null}{editor ? <form className={`card editor ${conflict ? "conflict" : ""}`} onSubmit={save}><div className="cluster" style={{ justifyContent: "space-between" }}><div><StatusBadge tone={editing?.status === "published" ? "signal" : "coral"}>{editing ? `${editing.status} · v${editing.version}` : "Nuevo borrador"}</StatusBadge><h2>{editing ? "Editar sesión" : "Crear sesión"}</h2></div><button className="button button-quiet" type="button" onClick={() => { setEditor(null); setEditing(null); }}>Cerrar ×</button></div>{conflict ? <div className="alert"><strong>El plan cambió mientras editabas.</strong><br />Tu copia no se sobrescribió. Recarga la versión publicada y decide qué cambios conservar.<div className="cluster" style={{ marginTop: 10 }}><button className="button button-danger" type="button" onClick={() => { setEditor(null); setEditing(null); load(); }}>Descartar mi copia y recargar</button><button className="button" type="button" onClick={() => setConflict(false)}>Seguir revisando mi copia</button></div></div> : null}<div className="form-grid"><label className="field"><span className="field-label">Título</span><input className="input" value={editor.title} onChange={(event) => setEditor({ ...editor, title: event.target.value })} required /></label><label className="field"><span className="field-label">Fecha</span><input className="input" type="date" value={editor.scheduled_date} onChange={(event) => setEditor({ ...editor, scheduled_date: event.target.value })} required /></label><label className="field"><span className="field-label">Deporte</span><select className="select" value={editor.sport_type} onChange={(event) => setEditor({ ...editor, sport_type: event.target.value as Sport })}><option value="running">Carrera</option><option value="cycling">Ciclismo</option><option value="swimming">Natación</option><option value="triathlon">Triatlón</option></select></label><label className="field"><span className="field-label">Bloque</span><select className="select" value={editor.block_id} onChange={(event) => setEditor({ ...editor, block_id: event.target.value })}><option value="">Sin bloque</option>{blocks.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label><label className="field span-all"><span className="field-label">Intención / nota para el atleta</span><textarea className="textarea" value={editor.description} onChange={(event) => setEditor({ ...editor, description: event.target.value })} /></label></div><SectionHeader title="Estructura" meta={<button className="button" type="button" onClick={() => setEditor({ ...editor, groups: [...editor.groups, blankGroup()] })}>+ Grupo</button>} />{editor.groups.map((group, groupIndex) => <section className="group-editor" key={groupIndex}><div className="group-header"><div className="cluster"><StatusBadge>Grupo {groupIndex + 1}</StatusBadge><label className="field"><span className="field-label">Repeticiones</span><input className="input" style={{ width: 92 }} type="number" min="1" max="100" value={group.repetitions} onChange={(event) => updateGroup(groupIndex, { repetitions: event.target.value })} /></label></div><button className="button button-danger" type="button" disabled={editor.groups.length === 1} onClick={() => setEditor({ ...editor, groups: editor.groups.filter((_, index) => index !== groupIndex) })}>Eliminar grupo</button></div>{group.steps.map((step, stepIndex) => <div key={stepIndex}><div className="step-row"><span className="step-number">{String(stepIndex + 1).padStart(2, "0")}</span><select className="select" aria-label={`Tipo del paso ${stepIndex + 1}`} value={step.kind} onChange={(event) => updateStep(groupIndex, stepIndex, { kind: event.target.value as StepKind })}><option value="warmup">Calentamiento</option><option value="work">Trabajo</option><option value="recovery">Recuperación</option><option value="cooldown">Vuelta a la calma</option></select><select className="select" aria-label={`Medida del paso ${stepIndex + 1}`} value={step.measure} onChange={(event) => updateStep(groupIndex, stepIndex, { measure: event.target.value as StepDraft["measure"] })}><option value="duration">Duración · segundos</option><option value="distance">Distancia · metros</option></select><input className="input" aria-label={`Cantidad del paso ${stepIndex + 1}`} type="number" min="1" value={step.amount} onChange={(event) => updateStep(groupIndex, stepIndex, { amount: event.target.value })} /><label className="cluster"><input type="checkbox" checked={step.target} onChange={(event) => updateStep(groupIndex, stepIndex, { target: event.target.checked })} /> Objetivo</label><button className="button icon-button button-danger" type="button" aria-label={`Eliminar paso ${stepIndex + 1}`} disabled={group.steps.length === 1} onClick={() => updateGroup(groupIndex, { steps: group.steps.filter((_, index) => index !== stepIndex) })}>×</button></div>{step.target ? <div className="target-fields"><select className="select" aria-label="Métrica del objetivo" value={step.metric} onChange={(event) => { const metric = event.target.value as TargetMetric; updateStep(groupIndex, stepIndex, { metric, unit: targetUnits[metric][0] }); }}><option value="pace">Ritmo</option><option value="power">Potencia</option><option value="heart_rate">Frecuencia cardiaca</option><option value="rpe">RPE</option></select><select className="select" aria-label="Unidad del objetivo" value={step.unit} onChange={(event) => updateStep(groupIndex, stepIndex, { unit: event.target.value as TargetUnit })}>{targetUnits[step.metric].map((unit) => <option key={unit} value={unit}>{unit}</option>)}</select><input className="input" aria-label="Objetivo mínimo" type="number" value={step.minimum} onChange={(event) => updateStep(groupIndex, stepIndex, { minimum: event.target.value })} placeholder="Mínimo" /><input className="input" aria-label="Objetivo máximo" type="number" value={step.maximum} onChange={(event) => updateStep(groupIndex, stepIndex, { maximum: event.target.value })} placeholder="Máximo" /></div> : null}</div>)}<button className="button button-quiet" type="button" onClick={() => updateGroup(groupIndex, { steps: [...group.steps, blankStep()] })}>+ Añadir paso</button></section>)}{editorError ? <ErrorState message={editorError} /> : null}<div className="publish-bar"><div><strong>{editing ? `Versión ${editing.version}` : "Borrador nuevo"}</strong><br /><span className="helper">Guardar nunca publica automáticamente.</span></div><div className="cluster"><button className="button" type="submit" disabled={saving || editing?.status === "published"}>{saving ? "Guardando…" : editing ? "Guardar cambios" : "Guardar borrador"}</button>{editing?.status === "draft" ? <button className="button button-primary" type="button" disabled={saving} onClick={publish}>Publicar versión {editing.version} ↗</button> : null}</div></div></form> : null}<SectionHeader title="Calendario" meta={<div className="cluster"><button className="button icon-button" aria-label="Mes anterior" onClick={() => shiftMonth(-1)}>←</button><button className="button" onClick={() => setAnchor(isoDay())}>Hoy</button><button className="button icon-button" aria-label="Mes siguiente" onClick={() => shiftMonth(1)}>→</button></div>} /><div className="calendar-toolbar"><strong className="calendar-title">{formatDay(range.start, { month: "long", year: "numeric" })}</strong><span className="helper">{workouts.length} sesiones · {blocks.length} bloques</span></div>{loading ? <div className="card" role="status">Actualizando calendario…</div> : workouts.length === 0 ? <EmptyState title="Este mes todavía no tiene sesiones." copy="Crea una sesión estructurada y guárdala como borrador antes de publicarla." action={<button className="button button-primary" onClick={() => openNew(range.start)}>Crear primera sesión</button>} /> : null}<div className="calendar-weekdays" aria-hidden="true">{["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"].map((day) => <span key={day}>{day}</span>)}</div><div className="calendar-grid" aria-label="Calendario mensual">{calendarDays.map((day) => <div className={`calendar-cell ${day.slice(0, 7) !== range.start.slice(0, 7) ? "outside" : ""}`} key={day}><button className="button button-quiet calendar-date" type="button" onClick={() => openNew(day)} aria-label={`Crear sesión el ${formatDay(day, { dateStyle: "long" })}`}>{day.slice(8, 10)}</button>{(workoutsByDay[day] ?? []).map((workout) => <button className={`workout-chip ${workout.status}`} type="button" key={workout.id} onClick={() => openExisting(workout)}><span className="metadata">{workout.sport_type === "running" ? "RUN" : workout.sport_type === "cycling" ? "BIKE" : workout.sport_type === "swimming" ? "SWIM" : "TRI"} · {workout.status}</span><small>{workout.title}</small></button>)}</div>)}</div><div className="agenda">{calendarDays.filter((day) => day.slice(0, 7) === range.start.slice(0, 7)).map((day) => <section className="agenda-day" key={day}><div className="cluster" style={{ justifyContent: "space-between" }}><strong>{formatDay(day, { weekday: "short", day: "numeric", month: "short" })}</strong><button className="button button-quiet" onClick={() => openNew(day)}>+ Sesión</button></div>{(workoutsByDay[day] ?? []).map((workout) => <button className={`workout-chip ${workout.status}`} key={workout.id} onClick={() => openExisting(workout)}><span>{workout.title}</span><small>{workout.status}</small></button>)}</section>)}</div><CompetitionsWorkspace athleteId={athleteId} editable /></div>;
}
