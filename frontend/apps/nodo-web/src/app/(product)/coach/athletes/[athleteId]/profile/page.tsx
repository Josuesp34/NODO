"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { WeekdayPicker } from "@/components/workout-fields";
import { CompetitionsWorkspace } from "@/components/competitions-workspace";
import { EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/ui";
import { nodoRequest, problemFrom } from "@/lib/api";

type Profile = {
  id: number;
  sports: string[];
  timezone: string;
  goals: Record<string, unknown>;
  availability: Record<string, unknown>;
  rest_hr: number | null;
  max_hr: number | null;
  ftp: number | null;
  threshold_pace_sec_per_km: number | null;
  trimp_variant: string | null;
  source: string;
  valid_from: string;
};

const blank = {
  sports: ["running"], timezone: "America/Mexico_City", goals: "", availability: [0,1,2,3,4,5,6], rest_hr: "", max_hr: "", ftp: "", threshold_pace_sec_per_km: "", trimp_variant: "", source: "manual", valid_from: new Date().toISOString().slice(0, 10),
};

function nextVersionDate(current?: string) {
  const today = new Date(); today.setUTCHours(0, 0, 0, 0);
  const afterCurrent = current ? new Date(`${current}T00:00:00Z`) : today;
  if (current) afterCurrent.setUTCDate(afterCurrent.getUTCDate() + 1);
  return new Date(Math.max(today.getTime(), afterCurrent.getTime())).toISOString().slice(0, 10);
}

export default function AthleteProfilePage() {
  const { athleteId } = useParams<{ athleteId: string }>();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [history, setHistory] = useState<(Profile & {valid_to?: string | null})[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [form, setForm] = useState(blank);

  useEffect(() => {
    void nodoRequest<(Profile & {valid_to?: string | null})[]>(`athletes/${athleteId}/profile/history`).then(setHistory).catch((reason)=>setError(problemFrom(reason).message));
    void nodoRequest<Profile>(`athletes/${athleteId}/profile`).then((value) => {
      setProfile(value);
      setForm({ sports: value.sports, timezone: value.timezone, goals: String(value.goals.objective ?? ""), availability: Array.isArray(value.availability.available_weekdays) ? value.availability.available_weekdays as number[] : [0,1,2,3,4,5,6], rest_hr: value.rest_hr?.toString() ?? "", max_hr: value.max_hr?.toString() ?? "", ftp: value.ftp?.toString() ?? "", threshold_pace_sec_per_km: value.threshold_pace_sec_per_km?.toString() ?? "", trimp_variant: value.trimp_variant ?? "", source: value.source, valid_from: nextVersionDate(value.valid_from) });
    }).catch((reason) => { if (problemFrom(reason).status !== 404) setError(problemFrom(reason).message); }).finally(() => setLoading(false));
  }, [athleteId]);

  function toggleSport(sport: string) {
    setForm((current) => ({ ...current, sports: current.sports.includes(sport) ? current.sports.filter((item) => item !== sport) : [...current.sports, sport] }));
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(null); setSaved(false);
    try {
      const payload = {
        ...form,
        goals: { ...(profile?.goals ?? {}), objective: form.goals },
        availability: { ...(profile?.availability ?? {}), available_weekdays: form.availability },
        rest_hr: form.rest_hr ? Number(form.rest_hr) : null,
        max_hr: form.max_hr ? Number(form.max_hr) : null,
        ftp: form.ftp ? Number(form.ftp) : null,
        threshold_pace_sec_per_km: form.threshold_pace_sec_per_km ? Number(form.threshold_pace_sec_per_km) : null,
        trimp_variant: form.trimp_variant || null,
      };
      if (!form.sports.length) throw new Error("Selecciona al menos un deporte.");
      const next = await nodoRequest<Profile>(`athletes/${athleteId}/profile`, { method: "PUT", body: payload });
      setProfile(next); setHistory([next,...history]); setSaved(true); setForm((current) => ({ ...current, valid_from: nextVersionDate(next.valid_from) }));
    } catch (reason) { setError(reason instanceof SyntaxError ? "Objetivos y disponibilidad deben ser JSON válido." : reason instanceof Error && !("status" in reason) ? reason.message : problemFrom(reason).message); }
  }

  return <div className="page page-narrow"><PageHeader eyebrow="Atleta / Perfil" title="Parámetros deportivos" description="Cada guardado crea una versión vigente; los datos fisiológicos nunca se sobreescriben sin fecha y fuente." />{loading ? <div className="card">Cargando perfil…</div> : <>{profile ? <div className="alert alert-info"><StatusBadge tone="signal">Vigente desde {profile.valid_from}</StatusBadge> La siguiente edición crea una nueva versión.</div> : <EmptyState title="Perfil aún no configurado." copy="Completa la primera versión para habilitar cálculos con fuente y vigencia." />}<form className="card stack" onSubmit={submit} style={{ marginTop: 18 }}><fieldset className="field"><legend className="field-label">Deportes</legend><div className="cluster">{[["running", "Carrera"], ["cycling", "Ciclismo"], ["swimming", "Natación"], ["triathlon", "Triatlón"]].map(([value, label]) => <label className="cluster" key={value}><input type="checkbox" checked={form.sports.includes(value)} onChange={() => toggleSport(value)} /> {label}</label>)}</div></fieldset><div className="form-grid"><label className="field"><span className="field-label">Zona horaria</span><input className="input" value={form.timezone} onChange={(event) => setForm({ ...form, timezone: event.target.value })} required /></label><label className="field"><span className="field-label">Vigente desde</span><input className="input" type="date" value={form.valid_from} onChange={(event) => setForm({ ...form, valid_from: event.target.value })} required /></label><label className="field"><span className="field-label">FC reposo</span><input className="input" type="number" min="1" value={form.rest_hr} onChange={(event) => setForm({ ...form, rest_hr: event.target.value })} /></label><label className="field"><span className="field-label">FC máxima</span><input className="input" type="number" min="1" value={form.max_hr} onChange={(event) => setForm({ ...form, max_hr: event.target.value })} /></label><label className="field"><span className="field-label">FTP · watts</span><input className="input" type="number" min="1" value={form.ftp} onChange={(event) => setForm({ ...form, ftp: event.target.value })} /></label><label className="field"><span className="field-label">Ritmo umbral · s/km</span><input className="input" type="number" min="1" value={form.threshold_pace_sec_per_km} onChange={(event) => setForm({ ...form, threshold_pace_sec_per_km: event.target.value })} /></label><label className="field"><span className="field-label">Variante TRIMP</span><select className="select" value={form.trimp_variant} onChange={(event) => setForm({ ...form, trimp_variant: event.target.value })}><option value="">Sin cálculo</option><option value="banister_male">Banister male</option><option value="banister_female">Banister female</option></select></label><label className="field"><span className="field-label">Fuente</span><input className="input" value={form.source} onChange={(event) => setForm({ ...form, source: event.target.value })} required /></label><label className="field"><span className="field-label">Objetivo deportivo</span><textarea className="textarea" value={form.goals} onChange={(event) => setForm({ ...form, goals: event.target.value })} /></label><WeekdayPicker value={form.availability} onChange={availability=>setForm({...form,availability})}/></div>{error ? <ErrorState message={error} /> : null}{saved ? <div className="alert alert-success" role="status">Nueva versión del perfil guardada.</div> : null}<button className="button button-primary">Guardar nueva versión</button></form><section className="card stack" style={{marginTop:18}}><h2>Historial de parámetros</h2>{history.map(version=><article key={version.id}><strong>{version.valid_from} — {version.valid_to ?? "sin fin definido"}</strong><p>Fuente {version.source} · {version.sports.join(" / ")} · {version.timezone}</p><p>FC {version.rest_hr ?? "sin dato"}/{version.max_hr ?? "sin dato"} · FTP {version.ftp ?? "sin dato"} W</p></article>)}</section><CompetitionsWorkspace athleteId={Number(athleteId)} editable /></>}</div>;
}
