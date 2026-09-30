"use client";
import { useParams } from "next/navigation";
import { ActivitiesWorkspace } from "@/components/activity-workspace";
export default function Page() { const {athleteId} = useParams<{athleteId:string}>(); const id=Number(athleteId); return Number.isInteger(id)&&id>0 ? <ActivitiesWorkspace athleteId={id} coach /> : <p role="alert">Atleta inválido.</p>; }
