"use client";

import { useParams } from "next/navigation";
import { PlanningWorkspace } from "@/components/planning-workspace";

export default function AthleteCalendarPage() {
  const { athleteId } = useParams<{ athleteId: string }>();
  const id = Number(athleteId);
  if (!Number.isInteger(id) || id < 1) return <main className="page"><p role="alert">El identificador del atleta no es válido.</p></main>;
  return <PlanningWorkspace athleteId={id} />;
}
