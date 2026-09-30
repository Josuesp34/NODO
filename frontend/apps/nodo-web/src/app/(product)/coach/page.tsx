"use client";

import Link from "next/link";
import { useSession } from "@/components/product-shell";
import { AthletesWorkspace } from "@/components/athletes-workspace";
import { PageHeader, SectionHeader } from "@/components/ui";

export default function CoachDashboard() {
  const { identity } = useSession();
  return <div className="page"><PageHeader eyebrow="Centro de mando" title={`Hola, ${identity.first_name}.`} description="Empieza por el atleta o la situación que necesita una decisión. NODO muestra únicamente prioridades sustentadas por señales registradas." actions={<Link className="button button-primary" href="/coach/athletes">Ver equipo ↗</Link>} /><div className="card-grid"><Link className="card metric-card" href="/coach/athletes"><span className="badge badge-signal">Disponible</span><div><span className="metric-value">Equipo</span><p className="muted">Atletas, invitaciones y planificación.</p></div></Link><Link className="card metric-card" href="/coach/review"><span className="badge badge-info">Disponible</span><div><span className="metric-value">Revisión</span><p className="muted">Molestias y señales con razón visible.</p></div></Link><Link className="card metric-card" href="/coach/copilot"><span className="badge">Simulación</span><div><span className="metric-value">Copiloto</span><p className="muted">Explora un borrador sin guardarlo.</p></div></Link></div><SectionHeader title="Tu equipo" meta={<Link className="button button-quiet" href="/coach/athletes">Ver todos</Link>} /><AthletesWorkspace compact /></div>;
}
