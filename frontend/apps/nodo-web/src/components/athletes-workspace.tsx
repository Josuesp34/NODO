"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { nodoRequest, problemFrom } from "@/lib/api";
import type { Athlete } from "@/lib/contracts";
import { EmptyState, ErrorState, StatusBadge } from "./ui";

type Invitation = { athlete: Athlete; invitation_token?: string; invitation_expires_at?: string };

export function AthletesWorkspace({ compact = false }: { compact?: boolean }) {
  const [athletes, setAthletes] = useState<Athlete[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviting, setInviting] = useState(false);
  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [form, setForm] = useState({ email: "", first_name: "", last_name: "", timezone: "America/Mexico_City" });

  function load() {
    setLoading(true); setError(null);
    void nodoRequest<Athlete[]>("auth/athletes").then(setAthletes).catch((reason) => setError(problemFrom(reason).message)).finally(() => setLoading(false));
  }
  useEffect(load, []);
  const visible = useMemo(() => athletes.filter((athlete) => `${athlete.first_name} ${athlete.last_name} ${athlete.email}`.toLowerCase().includes(query.toLowerCase())).slice(0, compact ? 6 : undefined), [athletes, compact, query]);

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setInviting(true); setError(null); setInvitation(null);
    try {
      const result = await nodoRequest<Invitation>("auth/athletes", { method: "POST", body: form });
      setAthletes((current) => [...current, result.athlete]); setInvitation(result);
      setForm({ email: "", first_name: "", last_name: "", timezone: "America/Mexico_City" });
    } catch (reason) { setError(problemFrom(reason).message); }
    finally { setInviting(false); }
  }

  return <div className="stack">{!compact ? <div className="cluster"><label className="field" style={{ flex: 1 }}><span className="field-label">Buscar atleta</span><input className="input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nombre o correo" /></label><button className="button button-primary" type="button" onClick={() => setInviteOpen((value) => !value)}>{inviteOpen ? "Cerrar" : "+ Invitar atleta"}</button></div> : null}{inviteOpen ? <form className="card stack" onSubmit={invite}><div className="cluster" style={{ justifyContent: "space-between" }}><div><StatusBadge tone="info">Invitación</StatusBadge><h2 style={{ marginBottom: 0 }}>Agregar atleta</h2></div><span className="helper">Activación segura de un solo uso</span></div><div className="form-grid"><label className="field"><span className="field-label">Nombre</span><input className="input" value={form.first_name} onChange={(event) => setForm({ ...form, first_name: event.target.value })} required /></label><label className="field"><span className="field-label">Apellido</span><input className="input" value={form.last_name} onChange={(event) => setForm({ ...form, last_name: event.target.value })} required /></label><label className="field"><span className="field-label">Correo</span><input className="input" type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /></label><label className="field"><span className="field-label">Zona horaria</span><select className="select" value={form.timezone} onChange={(event) => setForm({ ...form, timezone: event.target.value })}><option>America/Mexico_City</option><option>America/New_York</option><option>Europe/Madrid</option><option>UTC</option></select></label></div><button className="button button-primary" disabled={inviting}>{inviting ? "Creando…" : "Crear invitación"}</button>{invitation?.invitation_token ? <div className="alert alert-info"><strong>Código de activación</strong><br /><code style={{ overflowWrap: "anywhere" }}>{invitation.invitation_token}</code><br /><span className="helper">Compártelo únicamente con esta persona por un canal privado. Expira el {invitation.invitation_expires_at ? new Date(invitation.invitation_expires_at).toLocaleString("es-MX") : "plazo indicado"} y deja de funcionar después de usarse.</span></div> : invitation ? <div className="alert alert-success">Invitación creada. La entrega se gestionó sin exponer el código.</div> : null}</form> : null}{error ? <ErrorState message={error} retry={load} /> : null}{loading ? <div className="card" role="status">Cargando atletas…</div> : visible.length ? <div className="athlete-list">{visible.map((athlete) => <Link className="athlete-card" href={`/coach/athletes/${athlete.id}/calendar`} key={athlete.id}><div className="cluster" style={{ justifyContent: "space-between" }}><StatusBadge>Atleta</StatusBadge><span className="metadata subtle">#{athlete.id}</span></div><span className="athlete-avatar">{athlete.first_name[0]}{athlete.last_name[0]}</span><h2>{athlete.first_name} {athlete.last_name}</h2><p>{athlete.email}</p><footer>Abrir planificación ↗</footer></Link>)}</div> : !error ? <EmptyState title={query ? "No encontramos coincidencias." : "Aún no hay atletas."} copy={query ? "Prueba con otro nombre o correo." : "Crea la primera invitación para comenzar el recorrido completo."} /> : null}</div>;
}
