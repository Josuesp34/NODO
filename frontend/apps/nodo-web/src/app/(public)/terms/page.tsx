import Link from "next/link";
import { Brand } from "@/components/ui";

export default function TermsPage() {
  return <main className="public-shell" id="contenido"><header className="public-nav"><Brand /><Link className="button button-quiet" href="/">Volver</Link></header><section className="section" style={{ marginTop: 90 }}><div className="section-grid"><p className="eyebrow"><strong>LEGAL</strong> Piloto</p><div><h1 className="section-title">Términos pendientes de aprobación.</h1><p className="lead">NODO no diagnostica, no previene lesiones y no garantiza marcas ni rendimiento. El entrenador conserva la decisión final. Los términos definitivos del piloto y de terceros deben ser aprobados antes de cualquier operación con datos reales.</p><div className="alert alert-info">No se presenta este texto como contrato ni aceptación de términos.</div></div></div></section></main>;
}
