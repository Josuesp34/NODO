import { AthletesWorkspace } from "@/components/athletes-workspace";
import { PageHeader } from "@/components/ui";

export default function AthletesPage() {
  return <div className="page"><PageHeader eyebrow="NODO Lab / Equipo" title="Atletas" description="Busca, invita y abre el calendario de cada atleta. Cada acceso se verifica antes de mostrar información." /><AthletesWorkspace /></div>;
}
