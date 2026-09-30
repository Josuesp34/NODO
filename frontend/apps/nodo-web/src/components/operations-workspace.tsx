"use client";

import { useEffect, useState } from "react";
import { nodoRequest, problemFrom } from "@/lib/api";
import { useSession } from "./product-shell";
import { ErrorState, PageHeader } from "./ui";

type Operations = { observed_at: string; worker_last_seen_at: string | null; worker_recent: boolean; oldest_pending_age_seconds: number | null; stale_running_count: number; queue: { kind: string; status: string; count: number }[] };
export function OperationsWorkspace() {
  const { capabilities } = useSession();
  const [data, setData] = useState<Operations | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function load() { setError(null); try { setData(await nodoRequest<Operations>("admin/operations")); } catch (reason) { setError(problemFrom(reason).message); } }
  useEffect(() => { if (capabilities.includes("staff")) void load(); }, [capabilities]);
  if (!capabilities.includes("staff")) return <ErrorState message="Esta pantalla requiere administración." />;
  return <div className="page"><PageHeader eyebrow="Administración / Operación" title="Cola y worker" description="Estado del procesamiento interno. Una configuración presente requiere comprobación externa del proveedor." actions={<button className="button" onClick={load}>Actualizar</button>} />{error ? <ErrorState message={error} retry={load} /> : null}{data ? <><section className="card"><p role="status">Worker: {data.worker_recent ? "activo recientemente" : "sin señal reciente"}</p><p>Última señal: {data.worker_last_seen_at ?? "no registrada"}</p><p>Antigüedad pendiente: {data.oldest_pending_age_seconds == null ? "sin pendientes" : `${Math.round(data.oldest_pending_age_seconds)} s`} · Leases vencidos: {data.stale_running_count}</p></section><table><caption>Trabajos por tipo y estado</caption><thead><tr><th>Tipo</th><th>Estado</th><th>Cantidad</th></tr></thead><tbody>{data.queue.map((row) => <tr key={`${row.kind}:${row.status}`}><td>{row.kind}</td><td>{row.status}</td><td>{row.count}</td></tr>)}</tbody></table><p className="helper">Observado: {data.observed_at}. Consulte los runbooks antes de reintentar trabajos dead o restaurar datos.</p></> : !error ? <p role="status">Consultando operación…</p> : null}</div>;
}
