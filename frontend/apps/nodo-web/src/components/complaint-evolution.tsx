"use client";
import { FormEvent, useState } from "react";
import { nodoRequest, problemFrom } from "@/lib/api";
import { ErrorState, StatusBadge } from "./ui";
export type ComplaintRecord = {
  id: number;
  version: number;
  zone: string;
  laterality: string;
  intensity_0_10: number;
  started_on: string;
  limits_movement: boolean;
  status: string;
  note?: string | null;
};
type History = {
  complaint: ComplaintRecord;
  updates: {
    id: number;
    intensity_0_10: number;
    limits_movement: boolean;
    note: string | null;
    created_at: string;
  }[];
  decisions: { action: string; at: string; note: string | null }[];
  review: {
    status: string;
    reason: string;
    decision_note: string | null;
  } | null;
};
export function ComplaintEvolution({
  item,
  editable = false,
  onChanged,
}: {
  item: ComplaintRecord;
  editable?: boolean;
  onChanged?: () => void;
}) {
  const [history, setHistory] = useState<History | null>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    intensity_0_10: item.intensity_0_10,
    limits_movement: item.limits_movement,
    note: "",
  });
  async function load() {
    setError(null);
    try {
      setHistory(await nodoRequest<History>(`complaints/${item.id}`));
    } catch (reason) {
      setError(problemFrom(reason).message);
    }
  }
  async function update(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await nodoRequest(`complaints/${item.id}/updates`, {
        method: "POST",
        body: {
          ...form,
          expected_version: history?.complaint.version ?? item.version,
        },
      });
      await load();
      onChanged?.();
    } catch (reason) {
      setError(
        problemFrom(reason).status === 409
          ? "La molestia cambió. Recarga su evolución antes de guardar."
          : problemFrom(reason).message,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="stack">
      <button
        className="button"
        onClick={() => {
          setOpen(!open);
          if (!open) void load();
        }}
      >
        {open ? "Ocultar evolución" : "Evolución y revisión"}
      </button>
      {open ? (
        <>
          {error ? (
            <ErrorState message={error} retry={() => void load()} />
          ) : null}
          {history ? (
            <>
              <StatusBadge>
                {history.complaint.status} · v{history.complaint.version}
              </StatusBadge>
              {history.review ? (
                <p>
                  Revisión: {history.review.status} · {history.review.reason}
                </p>
              ) : null}
              {history.updates.map((update) => (
                <p key={update.id}>
                  {new Date(update.created_at).toLocaleString("es-MX")}:
                  intensidad {update.intensity_0_10}/10 ·{" "}
                  {update.limits_movement ? "con limitación" : "sin limitación"}
                  . {update.note}
                </p>
              ))}
              {history.decisions.map((decision, index) => (
                <p key={index}>
                  {new Date(decision.at).toLocaleString("es-MX")}:{" "}
                  {decision.action} · {decision.note}
                </p>
              ))}
              {!history.updates.length ? (
                <p className="helper">
                  Sin actualizaciones después del reporte inicial.
                </p>
              ) : null}
              {editable ? (
                <form className="stack" onSubmit={update}>
                  <h3>
                    {history.complaint.status === "closed"
                      ? "Reabrir molestia"
                      : "Registrar evolución"}
                  </h3>
                  <label className="field">
                    Intensidad actual · 0–10
                    <input
                      className="input"
                      type="number"
                      min={0}
                      max={10}
                      value={form.intensity_0_10}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          intensity_0_10: Number(event.target.value),
                        })
                      }
                      required
                    />
                  </label>
                  <label className="cluster">
                    <input
                      type="checkbox"
                      checked={form.limits_movement}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          limits_movement: event.target.checked,
                        })
                      }
                    />
                    Limita movimiento
                  </label>
                  <label className="field">
                    Nota
                    <textarea
                      className="textarea"
                      value={form.note}
                      onChange={(event) =>
                        setForm({ ...form, note: event.target.value })
                      }
                      maxLength={2000}
                    />
                  </label>
                  <p className="helper">
                    Un empeoramiento o una actualización después del cierre
                    vuelve a abrir la revisión.
                  </p>
                  <button className="button button-primary" disabled={busy}>
                    Guardar evolución
                  </button>
                </form>
              ) : null}
            </>
          ) : (
            <p role="status">Cargando evolución…</p>
          )}
        </>
      ) : null}
    </div>
  );
}
