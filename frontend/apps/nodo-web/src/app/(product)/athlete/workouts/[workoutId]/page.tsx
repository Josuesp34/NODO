"use client";

import { useParams } from "next/navigation";
import { WorkoutDetail } from "@/components/athlete-workouts";

export default function WorkoutDetailPage() {
  const { workoutId } = useParams<{ workoutId: string }>();
  return <WorkoutDetail workoutId={Number(workoutId)} />;
}
