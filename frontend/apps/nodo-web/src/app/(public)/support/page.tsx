import Link from "next/link";
import { Brand } from "@/components/ui";

export const dynamic = "force-dynamic";

function configuredContactUrl() {
  const value = process.env.NODO_CONTACT_URL?.trim();
  if (!value) return null;
  return /^(https:\/\/|mailto:)/i.test(value) ? value : null;
}

export default function SupportPage() {
  const contactUrl = configuredContactUrl();
  return (
    <main className="public-shell" id="contenido">
      <header className="public-nav">
        <Brand />
        <Link className="button button-quiet" href="/">
          Volver
        </Link>
      </header>
      <section className="section" style={{ marginTop: 90 }}>
        <div className="section-grid">
          <p className="eyebrow">
            <strong>SUPPORT</strong> Piloto acompañado
          </p>
          <div>
            <h1 className="section-title">Hablemos con contexto.</h1>
            <p className="lead">
              Durante el piloto, el soporte se coordina directamente con el equipo. Describe qué estabas haciendo,
              qué esperabas y qué ocurrió. Nunca envíes contraseñas, tokens ni archivos FIT por correo.
            </p>
            <div className="cluster">
              <Link className="button" href="/guide/fit">
                Ver guía de carga FIT
              </Link>
              {contactUrl ? (
                <a className="button button-primary" href={contactUrl}>
                  Contactar al equipo ↗
                </a>
              ) : null}
            </div>
            {!contactUrl ? (
              <div className="contract-state" role="status" style={{ marginTop: 18 }}>
                <strong>Canal comercial por configurar</strong>
                <p>El equipo publicará aquí su canal oficial antes de abrir el piloto. Si recibiste una invitación, responde por el mismo medio.</p>
              </div>
            ) : null}
          </div>
        </div>
      </section>
    </main>
  );
}
