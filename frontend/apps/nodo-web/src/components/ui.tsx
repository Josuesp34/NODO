import Link from "next/link";

export function Brand({ lab = false }: { lab?: boolean }) {
  return (
    <Link className="brand" href="/">
      <span className="brand-dot" aria-hidden="true" />
      NODO{lab ? <span className="brand-lab">/ LAB</span> : null}
    </Link>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <p className="eyebrow"><strong>●</strong>{eyebrow}</p>
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

export function SectionHeader({ title, meta }: { title: string; meta?: React.ReactNode }) {
  return <div className="section-header"><h2>{title}</h2>{meta}</div>;
}

export function LoadingState({ label = "Abriendo NODO" }: { label?: string }) {
  return <div className="loading-screen" role="status"><span className="status-dot" /> {label.toUpperCase()}</div>;
}

export function EmptyState({ title, copy, action }: { title: string; copy: string; action?: React.ReactNode }) {
  return <section className="empty-state"><div><span className="badge badge-signal">NODO / 00</span><h2>{title}</h2><p>{copy}</p>{action}</div></section>;
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="alert" role="alert"><strong>No se pudo completar la acción.</strong><br />{message}{retry ? <><br /><button className="button button-quiet" type="button" onClick={retry}>Reintentar</button></> : null}</div>;
}

export function ContractState({
  title,
  description,
  expected: _expected,
}: {
  title: string;
  description: string;
  expected: string;
}) {
  return (
    <section className="card contract-state">
      <span className="badge badge-info">En preparación</span>
      <div><h2>{title}</h2><p className="muted">{description}</p></div>
      <p className="helper">Esta función todavía no está habilitada para tu cuenta. El resto de NODO continúa disponible.</p>
    </section>
  );
}

export function StatusBadge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "signal" | "coral" | "info" }) {
  return <span className={`badge ${tone === "signal" ? "badge-signal" : tone === "coral" ? "badge-coral" : tone === "info" ? "badge-info" : ""}`}>{children}</span>;
}
