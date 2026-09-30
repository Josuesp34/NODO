"use client";
import { useParams } from "next/navigation";
import { ScenariosWorkspace } from "@/components/scenarios-workspace";
export default function Page() {
  const { athleteId } = useParams<{ athleteId: string }>();
  const id = Number(athleteId);
  return Number.isInteger(id) && id > 0 ? (
    <ScenariosWorkspace key={id} athleteId={id} />
  ) : (
    <p role="alert">Atleta inválido.</p>
  );
}
