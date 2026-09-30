"use client";

import Link from "next/link";
import { IntervalsConnection } from "./intervals-connection";
import { CompetitionsWorkspace } from "./competitions-workspace";
import { ComplaintEvolution, type ComplaintRecord } from "./complaint-evolution";
import { FormEvent, useEffect, useState } from "react";
import { useSession } from "./product-shell";
import { EmptyState, ErrorState, PageHeader, StatusBadge } from "./ui";
import { nodoRequest, problemFrom } from "@/lib/api";
import { dayInZone } from "@/lib/dates";

export function CheckInWorkspace() {
  const { identity } = useSession();
  const [form, setForm] = useState({ local_date: dayInZone(new Date(), identity.timezone), fatigue: "5", perceived_rest: "5", stress: "5", session_rpe: "", notes: "" });
  const [state, setState] = useState<"idle" | "saving" | "saved">("idle");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setState("saving"); setError(null);
    try {
      await nodoRequest(`athletes/${identity.id}/checkins/${form.local_date}`, {
        method: "PUT",
        body: { ...form, fatigue: Number(form.fatigue), perceived_rest: Number(form.perceived_rest), stress: Number(form.stress), session_rpe: form.session_rpe ? Number(form.session_rpe) : null, notes: form.notes || null },
      });
      setState("saved");
    } catch (reason) { setState("idle"); setError(problemFrom(reason).message); }
  }

  const ranges = [["fatigue", "Fatiga · 0 baja, 10 alta"], ["perceived_rest", "Descanso percibido · 0 bajo, 10 alto"], ["stress", "Estrés · 0 bajo, 10 alto"]] as const;
  return <div className="page page-narrow"><PageHeader eyebrow="Mi NODO / Reportar" title="¿Cómo llegas hoy?" description="Tu percepción completa lo que un dispositivo no puede observar. La ausencia de respuesta nunca se convierte en cero." /><form className="card stack" onSubmit={submit}><div className="form-grid"><label className="field"><span className="field-label">Fecha local</span><input className="input" type="date" value={form.local_date} onChange={(event) => setForm({ ...form, local_date: event.target.value })} required /></label>{ranges.map(([key, label]) => <label className="field" key={key}><span className="field-label">{label}</span><input className="input" type="range" min="0" max="10" value={form[key]} onChange={(event) => setForm({ ...form, [key]: event.target.value })} /><output>{form[key]}/10</output></label>)}<label className="field"><span className="field-label">RPE de sesión · opcional</span><input className="input" type="number" min="0" max="10" value={form.session_rpe} onChange={(event) => setForm({ ...form, session_rpe: event.target.value })} /></label><label className="field span-all"><span className="field-label">Nota opcional</span><textarea className="textarea" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label></div>{error ? <ErrorState message={error} /> : null}{state === "saved" ? <div className="alert alert-success" role="status">Check-in guardado para {form.local_date}.</div> : null}<button className="button button-primary" disabled={state === "saving"}>{state === "saving" ? "Guardando…" : "Guardar check-in"}</button></form></div>;
}

type Complaint = ComplaintRecord;

export function ComplaintsWorkspace({ createOnly = false }: { createOnly?: boolean }) {
  const { identity } = useSession();
  const [items, setItems] = useState<Complaint[]>([]);
  const [loading, setLoading] = useState(!createOnly);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [form, setForm] = useState({ zone: "", laterality: "not_applicable", intensity_0_10: "3", started_on: dayInZone(new Date(), identity.timezone), limits_movement: false, note: "" });
  const endpoint = `athletes/${identity.id}/complaints`;

  useEffect(() => {
    if (createOnly) return;
    void nodoRequest<Complaint[]>(endpoint).then(setItems).catch((reason) => setError(problemFrom(reason).message)).finally(() => setLoading(false));
  }, [createOnly, endpoint]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(null); setSaved(false);
    try {
      const created = await nodoRequest<Complaint>(endpoint, { method: "POST", body: { ...form, intensity_0_10: Number(form.intensity_0_10), note: form.note || null } });
      setItems((current) => [created, ...current]); setSaved(true);
      setForm({ zone: "", laterality: "not_applicable", intensity_0_10: "3", started_on: dayInZone(new Date(), identity.timezone), limits_movement: false, note: "" });
    } catch (reason) { setError(problemFrom(reason).message); }
  }

  return <div className="page page-narrow"><PageHeader eyebrow="Mi NODO / Molestias" title={createOnly ? "Reportar una molestia" : "Molestias"} description="Puedes reportar sin reloj. NODO registra evolución y revisión; no diagnostica ni autoriza el retorno tras una lesión." actions={!createOnly ? <Link className="button button-primary" href="/athlete/complaints/new">+ Reportar</Link> : <Link className="button" href="/athlete/complaints">Volver</Link>} />{createOnly ? <form className="card stack" onSubmit={submit}><div className="form-grid"><label className="field"><span className="field-label">Zona corporal</span><input className="input" value={form.zone} onChange={(event) => setForm({ ...form, zone: event.target.value })} placeholder="Ej. rodilla" required /></label><label className="field"><span className="field-label">Lateralidad</span><select className="select" value={form.laterality} onChange={(event) => setForm({ ...form, laterality: event.target.value })}><option value="not_applicable">No aplica</option><option value="left">Izquierda</option><option value="right">Derecha</option><option value="bilateral">Ambas</option><option value="center">Centro</option></select></label><label className="field"><span className="field-label">Intensidad percibida · 0–10</span><input className="input" type="number" min="0" max="10" value={form.intensity_0_10} onChange={(event) => setForm({ ...form, intensity_0_10: event.target.value })} required /></label><label className="field"><span className="field-label">Inicio</span><input className="input" type="date" value={form.started_on} onChange={(event) => setForm({ ...form, started_on: event.target.value })} required /></label><label className="field span-all cluster"><input type="checkbox" checked={form.limits_movement} onChange={(event) => setForm({ ...form, limits_movement: event.target.checked })} /> Limita movimiento o sesión</label><label className="field span-all"><span className="field-label">Nota opcional</span><textarea className="textarea" value={form.note} onChange={(event) => setForm({ ...form, note: event.target.value })} /></label></div>{error ? <ErrorState message={error} /> : null}{saved ? <div className="alert alert-success" role="status">Reporte guardado y enviado a revisión.</div> : null}<button className="button button-primary">Enviar reporte</button></form> : loading ? <div className="card">Cargando molestias…</div> : error ? <ErrorState message={error} /> : items.length ? <div className="stack">{items.map((item) => <article className="card" key={item.id}><div className="cluster" style={{ justifyContent: "space-between" }}><StatusBadge tone={item.intensity_0_10 >= 7 ? "coral" : "info"}>{item.status}</StatusBadge><span className="metadata">{item.started_on}</span></div><h2>{item.zone} · {item.laterality}</h2><p>Intensidad percibida: <strong>{item.intensity_0_10}/10</strong></p><p className="muted">{item.limits_movement ? "Afecta el movimiento o la sesión." : "No reporta limitación de movimiento."}</p><ComplaintEvolution item={item} editable onChanged={() => { void nodoRequest<Complaint[]>(`athletes/${identity.id}/complaints`).then(setItems); }} /></article>)}</div> : <EmptyState title="No hay molestias reportadas." copy="Si algo cambia, repórtalo aunque no uses un reloj." action={<Link className="button button-primary" href="/athlete/complaints/new">Reportar molestia</Link>} />}</div>;
}

type FitResult = { status: string; activity_id: number; trimp_status?: string };

export function ConnectionsWorkspace() {
  const { identity } = useSession();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!file) return;
    const body = new FormData(); body.set("file", file); setMessage(null); setBusy(true);
    try {
      const result = await nodoRequest<FitResult>(`athletes/${identity.id}/activities/fit`, { method: "POST", body });
      setMessage(result.status === "already_imported" ? `Este FIT ya estaba importado como actividad ${result.activity_id}.` : `Actividad ${result.activity_id} importada. Estado TRIMP: ${result.trimp_status ?? "no informado"}.`);
    } catch (reason) { setMessage(problemFrom(reason).message); }
    finally { setBusy(false); }
  }

  return (
    <div className="page page-narrow">
      <PageHeader
        eyebrow="Mi NODO / Datos"
        title="Conexiones"
        description="NODO conserva proveedor, método, unidad y antigüedad. Una conexión no se presenta como activa si el servidor no lo confirma."
      />
      <IntervalsConnection />
      <section className="card stack" style={{ marginTop: 18 }}>
        <StatusBadge>Respaldo manual disponible</StatusBadge>
        <h2>Cargar archivo FIT</h2>
        <p className="muted">
          El archivo se asocia a tu identidad autenticada. Nunca lo envíes por correo ni lo subas a Git.
        </p>
        <Link className="button" href="/guide/fit">
          Leer guía de carga FIT
        </Link>
        <form className="stack" onSubmit={upload}>
          <input
            className="input"
            type="file"
            accept=".fit,application/octet-stream"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            required
          />
          <button className="button button-primary" disabled={!file || busy}>
            Cargar de forma segura
          </button>
        </form>
        {message ? (
          <div className="alert alert-info" role="status">
            {message}
          </div>
        ) : null}
      </section>
    </div>
  );
}

type AthleteProfile = { id: number; athlete_id: number; sports: string[]; timezone: string; goals: Record<string, unknown>; availability: Record<string, unknown>; rest_hr?: number | null; max_hr?: number | null; ftp?: number | null; threshold_pace_sec_per_km?: number | null; source: string; valid_from: string; valid_to?: string | null };

export function SelfProfileWorkspace() {
  const { identity } = useSession();
  const [profile, setProfile] = useState<AthleteProfile | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { void nodoRequest<AthleteProfile>(`athletes/${identity.id}/profile`).then((value) => { setProfile(value); setState("ready"); }).catch((reason) => { const problem = problemFrom(reason); if (problem.status === 404) setState("empty"); else { setError(problem.message); setState("error"); } }); }, [identity.id]);
  return <div className="page page-narrow"><PageHeader eyebrow="Mi NODO / Perfil" title={`${identity.first_name} ${identity.last_name}`} description="Tu entrenador usa parámetros con fuente y vigencia; tú puedes revisar qué información está disponible." /><section className="card"><div className="stack"><div><span className="field-label">Correo</span><p>{identity.email}</p></div><div><span className="field-label">Zona horaria de cuenta</span><p>{identity.timezone}</p></div></div></section><section className="card stack" style={{ marginTop: 18 }}>{state === "loading" ? <p>Cargando perfil deportivo…</p> : state === "error" ? <ErrorState message={error ?? "No pudimos cargar el perfil."} /> : state === "empty" ? <EmptyState title="Tu perfil deportivo aún no está configurado." copy="Tu entrenador puede crear la primera versión desde NODO Lab." /> : profile ? <><div className="cluster"><StatusBadge tone="signal">Vigente desde {profile.valid_from}</StatusBadge><StatusBadge>{profile.source}</StatusBadge></div><h2>{profile.sports.join(" · ")}</h2><p>Zona horaria deportiva: <strong>{profile.timezone}</strong></p><div className="proof-flow"><div><span className="field-label">FC reposo</span><p>{profile.rest_hr ?? "Sin dato"}</p></div><div><span className="field-label">FC máxima</span><p>{profile.max_hr ?? "Sin dato"}</p></div><div><span className="field-label">FTP</span><p>{profile.ftp ?? "Sin dato"}</p></div><div><span className="field-label">Ritmo umbral</span><p>{profile.threshold_pace_sec_per_km ? `${profile.threshold_pace_sec_per_km} s/km` : "Sin dato"}</p></div></div></> : null}</section><CompetitionsWorkspace athleteId={identity.id} /></div>;
}
