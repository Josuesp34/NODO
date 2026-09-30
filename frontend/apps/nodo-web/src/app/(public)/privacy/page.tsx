import Link from "next/link";
import { Brand } from "@/components/ui";

export default function PrivacyPage() {
  return <main className="public-shell" id="contenido"><header className="public-nav"><Brand /><Link className="button button-quiet" href="/">Volver</Link></header><section className="section" style={{ marginTop: 90 }}><div className="section-grid"><p className="eyebrow"><strong>LEGAL</strong> Estado actual</p><div><h1 className="section-title">Privacidad sin promesas vacías.</h1><p className="lead">El aviso de privacidad definitivo requiere aprobación humana antes de invitar atletas reales. NODO está diseñado para compartir con proveedores sólo el contexto necesario, conservar fuentes y permisos, y permitir exportación, revocación y borrado cuando sus contratos operativos estén habilitados.</p><div className="alert alert-info">Este resumen describe la intención de producto; no sustituye el aviso legal definitivo.</div></div></div></section></main>;
}
