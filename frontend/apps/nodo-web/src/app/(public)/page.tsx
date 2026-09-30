import Link from "next/link";
import { Brand } from "@/components/ui";

export default function LandingPage() {
  return (
    <main className="public-shell" id="contenido">
      <header className="public-nav">
        <Brand />
        <nav className="public-links" aria-label="Navegación pública">
          <a href="#como-funciona">Cómo funciona</a>
          <a href="#control">Control</a>
          <Link className="button button-primary" href="/login">Entrar ↗</Link>
        </nav>
      </header>

      <section className="landing-hero">
        <div>
          <p className="eyebrow"><strong>00</strong> Entrenamiento con intención</p>
          <h1 className="display-title">Tu método.<br /><em>Cada atleta.</em></h1>
          <p className="lead">NODO ayuda a entrenadores de resistencia a planear, publicar y revisar entrenamiento personalizado sin perder el control de su metodología.</p>
          <div className="hero-actions">
            <Link className="button button-primary" href="/support">Solicitar acceso al piloto ↗</Link>
            <a className="button" href="#como-funciona">Ver el recorrido ↓</a>
          </div>
          <p className="helper" style={{ marginTop: 16 }}>Piloto acompañado. Sin precio público hasta cerrar la validación con entrenadores.</p>
        </div>
        <div className="node-visual" aria-label="El ciclo NODO conecta plan, ejecución y decisión">
          <span className="node-label one">01 / PLAN</span>
          <span className="node-label two">02 / EXECUTE</span>
          <span className="node-label three">03 / DECIDE</span>
          <span className="node-core">N<br />D</span>
        </div>
      </section>

      <section className="section" id="como-funciona">
        <div className="section-grid">
          <p className="eyebrow"><strong>01</strong> Un ciclo, no otra gráfica</p>
          <div><h2 className="section-title">Del plan a una decisión clara.</h2><p className="lead">La información vale cuando ayuda a elegir qué hacer después. NODO mantiene juntos el trabajo del entrenador, la ejecución y lo que el atleta reporta.</p></div>
        </div>
        <div className="proof-flow">
          {[
            ["01", "Estructura", "Crea bloques y sesiones por duración, distancia y objetivo."],
            ["02", "Publica", "El atleta recibe una sesión legible y enfocada en el día."],
            ["03", "Escucha", "Integra ejecución y contexto sin confundir ausencia con cero."],
            ["04", "Decide", "Revisa evidencia y aprueba cada cambio antes de aplicarlo."],
          ].map(([index, title, copy]) => <article className="proof-step" key={index}><span className="badge badge-signal">{index}</span><strong>{title}</strong><p>{copy}</p></article>)}
        </div>
      </section>

      <section className="section">
        <p className="eyebrow"><strong>02</strong> Diseñado para el trabajo real</p>
        <div className="feature-cards">
          <article className="feature-card"><span className="badge">NODO LAB</span><h3>Planea con criterio.</h3><p>Calendario, sesiones estructuradas, versiones y publicación bajo control del entrenador.</p></article>
          <article className="feature-card"><span className="badge">ATLETA</span><h3>Ejecuta con contexto.</h3><p>Hoy, semana y detalle de sesión en una PWA instalable y pensada primero para teléfono.</p></article>
          <article className="feature-card"><span className="badge">REVISIÓN</span><h3>Atiende lo importante.</h3><p>Molestias, datos faltantes y propuestas llegan con razones visibles; nunca se esconden detrás de una puntuación.</p></article>
        </div>
      </section>

      <section className="section" id="control">
        <div className="section-grid">
          <p className="eyebrow"><strong>03</strong> Control humano</p>
          <div className="trust-grid">
            <article className="trust-card"><h3>La IA propone. Tú decides.</h3><p>Los borradores se validan antes de guardar. Ninguna sesión se publica ni se modifica sin una acción explícita del entrenador.</p></article>
            <article className="trust-card"><h3>Datos con fuente y límites.</h3><p>NODO distingue lo observado, lo estimado y lo que falta. No diagnostica lesiones ni promete rendimiento.</p></article>
            <article className="trust-card"><h3>Una cuenta, tus capacidades.</h3><p>Quien entrena y también guía a otros usa una sola sesión con módulos separados y permisos verificados en servidor.</p></article>
            <article className="trust-card"><h3>Manual siempre disponible.</h3><p>El calendario y la edición estructurada siguen funcionando aunque un proveedor, reloj o copiloto no esté disponible.</p></article>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section-grid">
          <p className="eyebrow"><strong>04</strong> Piloto</p>
          <div><h2 className="section-title">Construyamos el siguiente ciclo.</h2><p className="lead">Buscamos entrenadores de carrera, ciclismo, natación y triatlón que quieran validar un flujo completo con acompañamiento.</p><div className="hero-actions"><Link className="button button-primary" href="/support">Quiero participar ↗</Link><Link className="button" href="/login">Ya tengo acceso</Link></div></div>
        </div>
      </section>

      <footer className="public-footer"><span>NODO TRAINING SYSTEMS / 2026</span><span><Link href="/privacy">Privacidad</Link> · <Link href="/terms">Términos</Link> · <Link href="/support">Soporte</Link></span></footer>
    </main>
  );
}
