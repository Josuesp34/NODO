import Link from "next/link";

export default function Landing() {
  return <main className="landing appShell">
    <header className="topbar landingNav"><Link className="brand" href="/"><span className="brandDot" />NODO</Link><nav><a href="#sistema">El sistema</a><a href="#para-quien">Para quién</a><Link className="navLogin" href="/login">Entrar <span>↗</span></Link></nav></header>
    <section className="landingHero"><div className="heroKicker"><span>00</span> TRAINING, WITH INTENTION</div><h1>Haz que cada<br /><em>sesión cuente.</em><span className="heroMark">✳</span></h1><p>NODO conecta la visión del entrenador con la ejecución del atleta. Un sistema para planear mejor, entrenar con contexto y avanzar con dirección.</p><div className="heroActions"><Link className="primary landingCta" href="/login"><span>ENTRAR A NODO</span><b>↗</b></Link><a className="textLink" href="#sistema">Conoce el sistema <span>↓</span></a></div></section>
    <div className="landingOrb" aria-hidden="true"><div className="orbRing ringOne" /><div className="orbRing ringTwo" /><div className="orbCore">N<br />D</div></div>
    <div className="landingTicker" aria-hidden="true"><span>PLAN / EXECUTE / EVOLVE</span><span>PLAN / EXECUTE / EVOLVE</span></div>
    <section className="landingManifesto" id="sistema"><div className="manifestoIndex">01 / THE NODE</div><div><h2>El entrenamiento no es una colección de datos.</h2><p>Es una conversación entre lo que planeas, lo que haces y lo que aprendes. NODO mantiene esas tres cosas en la misma dirección.</p></div></section>
    <section className="featureGrid" id="para-quien"><article><span>01</span><h3>Planea con criterio.</h3><p>Construye sesiones estructuradas y bloques que tengan una intención clara.</p><small>NODO LAB / COACHES</small></article><article><span>02</span><h3>Ejecuta con contexto.</h3><p>El atleta recibe una experiencia concreta, sin ruido y enfocada en el día.</p><small>NODO / ATHLETES</small></article><article><span>03</span><h3>Progresa con dirección.</h3><p>La carga, el ritmo y la conversación forman un mismo sistema de trabajo.</p><small>COMING IN THE NODE</small></article></section>
    <footer className="footerLine landingFooter"><span>NODO TRAINING SYSTEMS / 2026</span><span>DESIGNED FOR THE LONG RUN <i /></span></footer>
  </main>;
}
