"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { nodoRequest, problemFrom } from "@/lib/api";
import { useSession } from "./product-shell";
import { ErrorState, PageHeader } from "./ui";

type Usage = {
  estimated_completed_microusd: number;
  in_flight_reserved_microusd: number;
  uncertain_reserved_microusd: number;
  completed_requests: number;
  completed_input_tokens: number;
  completed_output_tokens: number;
};
type CostReport = {
  month_utc: string;
  totals: Usage;
  users: (Usage & { user_id: number; name: string; roles: string[] })[];
  budgets: {
    scope: string;
    scope_id: number;
    name?: string;
    requests: number;
    tokens: number;
    used_or_reserved_microusd: number;
    limit_microusd: number;
    active_athletes?: number;
    active_coaches?: number;
    budget_usage_per_active_athlete_microusd?: number | null;
    budget_usage_per_active_coach_microusd?: number | null;
  }[];
  explanation: string;
  pricing_note: string;
  allocation_note: string;
  pricing_current: {
    provider: string;
    model: string;
    input_usd_per_million: number;
    output_usd_per_million: number;
  };
};
const usd = (micros: number | null | undefined) =>
  micros == null
    ? "Sin denominador activo"
    : new Intl.NumberFormat("es-MX", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 6,
      }).format(micros / 1000000);

export function AiCostsWorkspace() {
  const { identity } = useSession();
  const admin = Boolean(identity.is_superuser);
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [data, setData] = useState<CostReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError(null);
    setLoading(true);
    void nodoRequest<CostReport>(
      `${admin ? "admin/commercial" : "account"}/ai-costs?month=${month}-01`,
      { signal: controller.signal },
    )
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((reason) => {
        if (!controller.signal.aborted) setError(problemFrom(reason).message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [admin, identity.id, month]);
  return (
    <div className="page">
      <PageHeader
        eyebrow="Ajustes / IA"
        title={admin ? "Uso y costos estimados de IA" : "Mi uso de IA"}
        description="El consumo de ambos asistentes se muestra en USD. Las reservas pendientes permanecen separadas del costo estimado de consultas completadas."
        actions={
          <Link className="button" href="/settings/commercial">
            Operación comercial
          </Link>
        }
      />
      <label className="field" style={{ maxWidth: 240 }}>
        Mes UTC
        <input
          className="input"
          type="month"
          value={month}
          min="2000-01"
          max="2100-12"
          required
          onChange={(event) => {
            if (event.target.value) setMonth(event.target.value);
          }}
        />
      </label>
      {error ? <ErrorState message={error} /> : null}
      {loading ? (
        <p role="status">Consultando uso guardado…</p>
      ) : data ? (
        <div className="stack" style={{ marginTop: 20 }}>
          <section className="card stack">
            <h2>Período {data.month_utc.slice(0, 7)}</h2>
            <p>{data.explanation}</p>
            <dl>
              <dt>Estimación de consultas completadas</dt>
              <dd>{usd(data.totals.estimated_completed_microusd)}</dd>
              <dt>Reservado para consultas en curso</dt>
              <dd>{usd(data.totals.in_flight_reserved_microusd)}</dd>
              <dt>Reserva con consumo externo por confirmar</dt>
              <dd>{usd(data.totals.uncertain_reserved_microusd)}</dd>
              <dt>Consultas completadas</dt>
              <dd>{data.totals.completed_requests}</dd>
              <dt>Tokens completados · entrada / salida</dt>
              <dd>
                {data.totals.completed_input_tokens} /{" "}
                {data.totals.completed_output_tokens}
              </dd>
            </dl>
          </section>
          <section className="card stack">
            <h2>{admin ? "Por cuenta de atleta o coach" : "Mi cuenta"}</h2>
            {!data.users.length ? (
              <p>Sin ejecuciones ni reservas guardadas en este período.</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table>
                  <caption>Una cuenta multirol aparece una sola vez</caption>
                  <thead>
                    <tr>
                      <th>Cuenta</th>
                      <th>Capacidades actuales</th>
                      <th>Completado estimado</th>
                      <th>Reserva en curso</th>
                      <th>Reserva por confirmar</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.users.map((user) => (
                      <tr key={user.user_id}>
                        <td>{user.name}</td>
                        <td>
                          {user.roles
                            .map((role) =>
                              role === "athlete"
                                ? "Atleta"
                                : role === "coach"
                                  ? "Coach"
                                  : role,
                            )
                            .join(", ")}
                        </td>
                        <td>{usd(user.estimated_completed_microusd)}</td>
                        <td>{usd(user.in_flight_reserved_microusd)}</td>
                        <td>{usd(user.uncertain_reserved_microusd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <section className="card stack">
            <h2>Presupuestos configurados y uso conservador</h2>
            <p className="helper">
              Los presupuestos de organización y usuario registran los mismos
              usos en ámbitos distintos; no se suman.
            </p>
            <p className="helper">{data.allocation_note}</p>
            {data.budgets.length ? (
              data.budgets.map((budget) => (
                <article
                  className="stack"
                  key={`${budget.scope}:${budget.scope_id}`}
                >
                  <h3>{budget.name ?? `Cuenta ${budget.scope_id}`}</h3>
                  <p>
                    Uso o reserva: {usd(budget.used_or_reserved_microusd)} de{" "}
                    {usd(budget.limit_microusd)} · {budget.requests} solicitudes
                    · {budget.tokens} tokens.
                  </p>
                  {budget.active_athletes !== undefined ? (
                    <p>
                      Reparto matemático del uso presupuestario:{" "}
                      {usd(budget.budget_usage_per_active_athlete_microusd)} por
                      atleta activo ({budget.active_athletes});{" "}
                      {usd(budget.budget_usage_per_active_coach_microusd)} por
                      coach activo ({budget.active_coaches}). Estas medias
                      incluyen reservas.
                    </p>
                  ) : null}
                </article>
              ))
            ) : (
              <p>No hay un contador presupuestario guardado para este mes.</p>
            )}
          </section>
          <section className="card stack">
            <h2>Tarifas configuradas actualmente</h2>
            <p>
              {data.pricing_current.provider} ·{" "}
              {data.pricing_current.model || "modelo por configurar"}. Entrada:
              USD {data.pricing_current.input_usd_per_million} / millón de
              tokens; salida: USD {data.pricing_current.output_usd_per_million}{" "}
              / millón.
            </p>
            <p>{data.pricing_note}</p>
            <p className="helper">
              La tarifa y el proveedor requieren verificación operativa. Este
              panel no consulta facturación externa ni incluye infraestructura.
            </p>
          </section>
        </div>
      ) : null}
    </div>
  );
}
