"use client";
import { useParams } from "next/navigation";
import { ActivityDetailWorkspace } from "@/components/activity-workspace";
export default function Page() { const {activityId} = useParams<{activityId:string}>(); const id=Number(activityId); return Number.isInteger(id)&&id>0 ? <ActivityDetailWorkspace activityId={id} /> : <p role="alert">Actividad inválida.</p>; }
