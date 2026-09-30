import Link from "next/link";
import { Brand } from "@/components/ui";

export default function OfflinePage() {
  return <main className="auth-page" id="contenido"><header className="public-nav"><Brand /></header><div className="auth-wrap"><section className="auth-copy"><p className="eyebrow"><strong>OFFLINE</strong> Sin conexión</p><h1>Tu señal<br /><em>volverá.</em></h1><p className="lead">NODO no pudo abrir una página nueva. Si ya consultaste tu entrenamiento de hoy, vuelve a ese módulo para usar la última copia guardada en este dispositivo.</p><Link className="button button-primary" href="/athlete/today">Abrir mi día ↗</Link></section></div></main>;
}
