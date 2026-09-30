import Link from "next/link";
import { Brand, StatusBadge } from "@/components/ui";

const results = [
  ["Importada", "La actividad quedó asociada a tu cuenta."],
  ["Ya importada", "NODO reconoció el mismo archivo y no creó un duplicado."],
  ["TRIMP sin datos suficientes", "La actividad se guardó, pero faltó perfil o resumen cardiaco para calcular carga."],
  ["Consentimiento requerido", "Autoriza el procesamiento en Ajustes → Privacidad y vuelve a intentar."],
] as const;

export default function FitGuidePage() {
  return (
    <main className="public-shell" id="contenido">
      <header className="public-nav">
        <Brand />
        <Link className="button button-quiet" href="/support">Soporte</Link>
      </header>
      <section className="section" style={{ marginTop: 90 }}>
        <div className="section-grid">
          <p className="eyebrow"><strong>GUIDE / FIT</strong> Datos de actividad</p>
          <div>
            <h1 className="section-title">Carga tu actividad de forma segura.</h1>
            <p className="lead">Usa el archivo FIT original de una sola sesión. NODO lo asocia a tu cuenta, evita duplicados y conserva únicamente los datos disponibles.</p>
            <div className="stack" style={{ marginTop: 28 }}>
              <article className="card"><StatusBadge tone="signal">01</StatusBadge><h2>Exporta el archivo</h2><p className="muted">Descarga la actividad en formato .fit desde la plataforma de tu reloj o ciclocomputador. El archivo debe pesar menos de 10 MiB.</p></article>
              <article className="card"><StatusBadge tone="signal">02</StatusBadge><h2>Abre Conexiones</h2><p className="muted">Entra a Mi NODO → Conexiones y localiza “Cargar archivo FIT”. No lo envíes por correo ni lo publiques en una carpeta compartida.</p></article>
              <article className="card"><StatusBadge tone="signal">03</StatusBadge><h2>Selecciona y confirma</h2><p className="muted">Comprueba que estás en la cuenta correcta, elige el archivo y pulsa “Cargar de forma segura”.</p></article>
            </div>
          </div>
        </div>
      </section>
      <section className="section">
        <div className="section-grid">
          <p className="eyebrow"><strong>RESULT</strong> Qué significa</p>
          <div className="stack">
            {results.map(([title, copy]) => <article className="trust-card" key={title}><h3>{title}</h3><p>{copy}</p></article>)}
          </div>
        </div>
      </section>
      <section className="section">
        <div className="section-grid">
          <p className="eyebrow"><strong>SYNC</strong> Intervals.icu</p>
          <div>
            <h2 className="section-title">La sincronización real aún no está activa.</h2>
            <p className="lead">“Probar simulación” no comparte credenciales ni descarga actividades. Hasta que NODO confirme una conexión real y su última sincronización, sigue usando FIT.</p>
            <Link className="button button-primary" href="/athlete/connections">Abrir Conexiones ↗</Link>
          </div>
        </div>
      </section>
    </main>
  );
}
