"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { nodoRequest, problemFrom } from "@/lib/api";
export default function IntervalsCallback() {
  const started = useRef(false);
  const [message, setMessage] = useState("Completando autorización…");
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const query = new URL(window.location.href).searchParams;
    const state = query.get("state"), code = query.get("code"), error = query.get("error");
    window.history.replaceState(null, "", window.location.pathname);
    if (!state) { setMessage("La autorización no contiene un estado válido. Vuelve a conectar."); return; }
    void nodoRequest("connections/intervals/callback", { method: "POST", body: { state, code, error } })
      .then(() => setMessage("Conexión autorizada. La importación inicial está en cola."))
      .catch((e) => setMessage(problemFrom(e).message));
  }, []);
  return <div className="page page-narrow"><h1>Conexión con Intervals.icu</h1><p role="status">{message}</p><Link className="button" href="/athlete/connections">Volver a conexiones</Link></div>;
}
