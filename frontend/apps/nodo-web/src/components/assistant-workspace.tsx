"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { nodoRequest, problemFrom } from "@/lib/api";
import type { Athlete } from "@/lib/contracts";
import { useSession } from "./product-shell";
import { ErrorState, PageHeader } from "./ui";

type Citation = { key?: string; entity: string; id: string | number; athlete_id: number; tool?: string; start?: string; end?: string };
type Message = { id: number; author: string; content: string; citations: Citation[] };
type Thread = { id: number; title: string; athlete_scope_id: number | null };
type Confirmation = { id: number; operation: string; payload: Record<string, unknown>; payload_hash: string; expires_at: string };
type Answer = { message: string; citations: Citation[]; confirmation: Confirmation | null; run_id: number };
type ProviderStatus = { provider: string; user_usage: { requests: number; estimated_cost_microusd: number } };

export function AssistantWorkspace({ role }: { role: "coach" | "athlete" }) {
  const { identity } = useSession();
  const [athletes, setAthletes] = useState<Athlete[]>([]);
  const [scope, setScope] = useState(role === "athlete" ? String(identity.id) : "");
  const [threads, setThreads] = useState<Thread[]>([]);
  const [threadId, setThreadId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [confirmations, setConfirmations] = useState<Confirmation[]>([]);
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [source, setSource] = useState<{ data: Record<string, unknown>[]; next_offset?: number | null } | null>(null);
  const [status, setStatus] = useState<ProviderStatus | null>(null);
  const abort = useRef<AbortController | null>(null);
  const runId = useRef<number | null>(null);
  const requestKey = useRef<string | null>(null);
  const sending = useRef(false);

  const refresh = useCallback(async (id: number) => {
    const [history, pending] = await Promise.all([
      nodoRequest<Message[]>(`assistant/threads/${id}/messages`),
      nodoRequest<Confirmation[]>(`assistant/threads/${id}/confirmations`),
    ]);
    setMessages(history); setConfirmations(pending);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      nodoRequest<Thread[]>(`assistant/threads?role=${role}`, { signal: controller.signal }),
      nodoRequest<ProviderStatus>("assistant/status", { signal: controller.signal }),
      role === "coach" ? nodoRequest<Athlete[]>("auth/athletes", { signal: controller.signal }) : Promise.resolve([]),
    ]).then(([history, provider, choices]) => {
      setThreads(history); setStatus(provider); setAthletes(choices);
    }).catch((e) => { if (!controller.signal.aborted) setError(problemFrom(e).message); });
    return () => { controller.abort(); abort.current?.abort(); };
  }, [identity.id, role]);

  useEffect(() => {
    setMessages([]); setConfirmations([]); setSource(null); setError(null);
    if (threadId) void refresh(threadId).catch((e) => setError(problemFrom(e).message));
  }, [threadId, refresh]);

  async function newThread() {
    const thread = await nodoRequest<Thread>("assistant/threads", { method: "POST", body: {
      role, athlete_scope_id: scope ? Number(scope) : null, title: role === "coach" ? "Consulta de entrenamiento" : "Mi entrenamiento",
    } });
    setThreads((old) => [thread, ...old]); setThreadId(thread.id); return thread.id;
  }

  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (sending.current || !prompt.trim()) return;
    sending.current = true; setBusy(true); setError(null); setNotice(null);
    const controller = new AbortController(); abort.current = controller;
    requestKey.current ??= crypto.randomUUID();
    let id = threadId;
    try {
      id ??= await newThread();
      const response = await fetch(`/api/nodo/assistant/threads/${id}/messages/stream`, {
        method: "POST", signal: controller.signal, credentials: "same-origin", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: prompt.trim(), request_key: requestKey.current }),
      });
      if (!response.ok) { const data = await response.json(); throw new Error(data.detail ?? "No se pudo enviar"); }
      const reader = response.body?.getReader();
      if (!reader) throw new Error("No se pudo abrir la respuesta");
      const decoder = new TextDecoder(); let buffer = "";
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        const events = buffer.split("\n\n"); buffer = events.pop() ?? "";
        for (const item of events) {
          if (!item.startsWith("data:")) continue;
          const event = JSON.parse(item.slice(5)) as { type: string; run_id?: number; result?: Answer; detail?: string };
          if (event.type === "run") runId.current = event.run_id ?? null;
          if (event.type === "error") throw new Error(event.detail);
          if (event.type === "result" && event.result) {
            setPrompt(""); requestKey.current = null;
            await refresh(id);
            setStatus(await nodoRequest<ProviderStatus>("assistant/status"));
          }
        }
      }
    } catch (e) {
      if (controller.signal.aborted) { setNotice("Petición cancelada. Puedes continuar con los formularios manuales."); requestKey.current = null; }
      else setError(e instanceof Error ? e.message : problemFrom(e).message);
      if (id) await refresh(id).catch(() => undefined);
    } finally { sending.current = false; setBusy(false); runId.current = null; abort.current = null; }
  }

  async function cancel() {
    if (runId.current) await nodoRequest(`assistant/runs/${runId.current}/cancel`, { method: "POST" }).catch(() => undefined);
    abort.current?.abort();
  }

  async function confirm(item: Confirmation) {
    if (sending.current) return;
    sending.current = true; setBusy(true); setError(null);
    try {
      const result = await nodoRequest<{ entity: string; id: number; status?: string }>(`assistant/confirmations/${item.id}`, {
        method: "POST", body: { payload_hash: item.payload_hash },
      });
      // Re-read the written resource, not just the confirmation response.
      const aid = Number(item.payload.athlete_id);
      if (result.entity === "complaint") await nodoRequest(`athletes/${aid}/complaints`);
      else {
        const day = String(item.payload.scheduled_date).slice(0, 10);
        const stored = await nodoRequest<{ id: number }[]>(`athletes/${aid}/workouts?start=${day}&end=${day}`);
        if (!stored.some((w) => w.id === result.id)) throw new Error("No se pudo verificar el borrador guardado");
      }
      setNotice(result.entity === "complaint" ? "Molestia registrada." : "Borrador guardado. Revisa y publica desde el calendario.");
      if (threadId) await refresh(threadId);
    } catch (e) { setError(problemFrom(e).message); }
    finally { sending.current = false; setBusy(false); }
  }

  async function openSource(citation: Citation) {
    setError(null);
    try { setSource(await nodoRequest<{ data: Record<string, unknown>[]; next_offset?: number | null }>(`assistant/tools/read?role=${role}`, { method: "POST", body: {
      tool: citation.tool ?? citation.entity, athlete_id: citation.athlete_id,
      ...(citation.start && citation.end ? { start: citation.start, end: citation.end } : {}), limit: 100,
    } })); } catch (e) { setError(problemFrom(e).message); }
  }

  return <div className="page page-narrow">
    <PageHeader eyebrow={role === "coach" ? "NODO Lab / Asistente" : "Mi NODO / Asistente"} title="Consulta tus datos y revisa propuestas." description="Conversaciones guardadas por rol. Cada escritura requiere revisar y confirmar." />
    {status?.provider === "simulated" ? <p className="alert alert-info">Modo simulado: consulta datos autorizados, sin modelo externo.</p> : null}
    {status ? <p className="helper">Solicitudes del mes: {status.user_usage.requests}. Costo estimado y reservas: ${(status.user_usage.estimated_cost_microusd / 1000000).toFixed(4)} USD.</p> : null}
    <div className="card stack">
      {role === "coach" ? <label className="field"><span>Atleta para una conversación nueva</span><select className="input" value={scope} disabled={busy} onChange={(e) => setScope(e.target.value)}><option value="">Resumen de mis atletas</option>{athletes.map((a) => <option key={a.id} value={a.id}>{a.first_name} {a.last_name}</option>)}</select></label> : null}
      <label className="field"><span>Conversación</span><select className="input" disabled={busy} value={threadId ?? ""} onChange={(e) => setThreadId(e.target.value ? Number(e.target.value) : null)}><option value="">Nueva conversación</option>{threads.map((t) => <option key={t.id} value={t.id}>{t.title} · {t.id}</option>)}</select></label>
      {error ? <ErrorState message={error} /> : null}{notice ? <p role="status" className="alert">{notice}</p> : null}
      <section aria-label="Historial del asistente" aria-live="polite" className="stack">{messages.map((m) => <article key={m.id} className="card"><strong>{m.author === "user" ? "Tú" : "NODO"}</strong><p style={{ whiteSpace: "pre-wrap" }}>{m.content}</p><div className="cluster">{m.citations.map((c, i) => <button key={`${c.key}-${i}`} type="button" className="button button-quiet" onClick={() => void openSource(c)}>Fuente: {c.entity} {c.id}</button>)}</div></article>)}</section>
      {confirmations.map((c) => <article key={c.id} className="card stack"><strong>Vista previa · {c.operation === "create_complaint" ? "Registrar molestia" : "Crear borrador"}</strong><PreviewPayload operation={c.operation} payload={c.payload} /><p className="helper">Vence: {new Date(c.expires_at).toLocaleString()}</p><button type="button" className="button button-primary" disabled={busy} onClick={() => void confirm(c)}>Confirmar y guardar</button></article>)}
      <form onSubmit={send} className="stack"><label className="field"><span>Tu mensaje</span><textarea className="textarea" maxLength={8000} value={prompt} disabled={busy} onChange={(e) => { setPrompt(e.target.value); requestKey.current = null; }} required /></label><div className="cluster"><button className="button button-primary" disabled={busy || !prompt.trim()}>{busy ? "Consultando…" : "Enviar"}</button>{busy ? <button type="button" className="button" onClick={() => void cancel()}>Cancelar</button> : null}</div></form>
      <p className="helper">También puedes <Link href={role === "coach" ? "/coach/athletes" : "/athlete/complaints"}>{role === "coach" ? "planificar manualmente" : "registrar una molestia manualmente"}</Link>.</p>
    </div>
    {source !== null ? <section className="card stack" aria-label="Fuente autorizada"><strong>Fuente consultada</strong><div className="stack">{source.data.map((row, index) => <dl className="card" key={index}>{Object.entries(row).map(([key, value]) => <div key={key}><dt className="helper">{fieldLabel(key)}</dt><dd style={{ overflowWrap: "anywhere" }}>{displayValue(value)}</dd></div>)}</dl>)}{source.next_offset ? <p className="helper">Hay más registros para este período. Consulta el historial del atleta para verlos todos.</p> : null}</div><button type="button" className="button" onClick={() => setSource(null)}>Cerrar fuente</button></section> : null}
  </div>;
}


function fieldLabel(key: string) {
  const labels: Record<string, string> = {
    id: "Referencia", title: "Sesión", scheduled_date: "Fecha", sport_type: "Disciplina", steps: "Estructura",
    source: "Origen", provider: "Origen", method: "Método", quality: "Calidad", metric_type: "Métrica",
    value: "Valor", unit: "Unidad", observed_start: "Inicio de medición", observed_end: "Fin de medición",
    timezone: "Zona horaria", start_time: "Inicio", total_duration_sec: "Duración (s)", total_distance_m: "Distancia (m)",
    calculated_trimp: "TRIMP calculado", calculated_tss: "TSS calculado", rest_hr: "FC reposo", max_hr: "FC máxima",
    sports: "Disciplinas", goals: "Objetivos", availability: "Disponibilidad", note: "Nota", reason: "Motivo",
    status: "Estado", version: "Versión", updates: "Seguimiento", daily_load: "Carga diaria", competitions: "Competencias",
  };
  return labels[key] ?? key.replaceAll("_", " ");
}
function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "Sin datos";
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
function PreviewPayload({ operation, payload }: { operation: string; payload: Record<string, unknown> }) {
  const fields = operation === "create_complaint"
    ? [["zone", "Zona"], ["laterality", "Lado"], ["intensity_0_10", "Intensidad (0–10)"], ["started_on", "Inicio"], ["limits_movement", "Limita movimiento"], ["note", "Nota"]]
    : [["title", "Sesión"], ["scheduled_date", "Fecha y hora"], ["sport_type", "Disciplina"], ["description", "Descripción"], ["steps", "Estructura"]];
  return <dl>{fields.map(([key, label]) => <div key={key}><dt className="helper">{label}</dt><dd style={{ overflowWrap: "anywhere" }}>{displayValue(payload[key])}</dd></div>)}</dl>;
}
