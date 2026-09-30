"use client";

import { useCallback, useEffect, useState } from "react";
import { nodoRequest, problemFrom } from "@/lib/api";
import { useSession } from "./product-shell";
import { ErrorState } from "./ui";

type Connection = { status: string; last_sync_at: string | null; sync_status: string | null };
export function IntervalsConnection() {
  const { identity } = useSession();
  const [connection, setConnection] = useState<Connection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const base = `connections/intervals/${identity.id}`;
  const refresh = useCallback(async () => setConnection(await nodoRequest<Connection>(base)), [base]);
  useEffect(() => { void refresh().catch((e) => setError(problemFrom(e).message)); }, [refresh]);
  async function action(kind: "authorize" | "sync" | "disconnect") {
    if (busy) return; setBusy(true); setError(null);
    try {
      if (kind === "authorize") {
        const result = await nodoRequest<{ authorization_url: string }>(`${base}/authorize`, { method: "POST" });
        const url = new URL(result.authorization_url);
        if (url.origin !== "https://intervals.icu" || url.pathname !== "/oauth/authorize") throw new Error("Enlace de autorización inválido");
        window.location.assign(url.href);
      } else { await nodoRequest(kind === "sync" ? `${base}/sync` : base, { method: kind === "sync" ? "POST" : "DELETE" }); await refresh(); }
    } catch (e) { setError(problemFrom(e).message); } finally { setBusy(false); }
  }
  return <section className="card stack"><h2>Intervals.icu</h2><p>Importa actividades directas y datos de bienestar. Tu plan se administra en NODO.</p>{error ? <ErrorState message={error} /> : null}<p>Estado: {connection?.status ?? "Consultando…"}</p><p className="helper">Última sincronización: {connection?.last_sync_at ? new Date(connection.last_sync_at).toLocaleString() : "Sin sincronización completada"}. Trabajo: {connection?.sync_status ?? "—"}</p><div className="cluster"><button type="button" className="button button-primary" disabled={busy} onClick={() => void action("authorize")}>{connection?.status === "not_connected" ? "Conectar Intervals" : "Reconectar / autorizar"}</button>{connection && ["connected", "syncing"].includes(connection.status) ? <button className="button" disabled={busy} onClick={() => void action("sync")}>Sincronizar</button> : null}{connection && connection.status !== "not_connected" && connection.status !== "revoked" ? <button className="button" disabled={busy} onClick={() => void action("disconnect")}>Desconectar</button> : null}<button className="button button-quiet" disabled={busy} onClick={() => void refresh().catch((e) => setError(problemFrom(e).message))}>Actualizar estado</button></div><p className="helper">Puedes seguir importando FIT manualmente. Intervals requiere una aplicación aprobada y tu consentimiento de lectura; no se solicita escritura.</p></section>;
}
