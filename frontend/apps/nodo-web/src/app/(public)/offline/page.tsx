import Link from "next/link";
import { Brand } from "@/components/ui";
import { OfflineWorkspace } from "@/components/offline-workspace";

export default function OfflinePage() {
  return <main className="auth-page" id="contenido"><header className="public-nav"><Brand /><Link href="/">Inicio</Link></header><OfflineWorkspace /></main>;
}
