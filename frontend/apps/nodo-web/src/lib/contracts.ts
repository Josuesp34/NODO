export type Capability = "athlete" | "coach" | "staff";

export type Identity = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  timezone: string;
  role?: "athlete" | "coach";
  roles?: Capability[];
  capabilities?: string[];
  coach_id?: number | null;
  is_superuser?: boolean;
};

export function capabilitiesFor(identity: Identity): Capability[] {
  const resolved = new Set<Capability>();
  if (identity.role) resolved.add(identity.role);
  for (const role of identity.roles ?? []) resolved.add(role);
  for (const capability of identity.capabilities ?? []) {
    const scope = capability.split(":", 1)[0];
    if (scope === "athlete" || scope === "coach" || scope === "staff") resolved.add(scope);
  }
  if (identity.is_superuser) resolved.add("staff");
  return Array.from(resolved);
}

export type Athlete = Identity & { id: number };

export type Block = {
  id: number;
  athlete_id: number;
  coach_id: number;
  title: string;
  start_date: string;
  end_date: string;
};

export type Sport = "running" | "cycling" | "swimming";
export type StepKind = "warmup" | "work" | "recovery" | "cooldown";
export type TargetMetric = "pace" | "power" | "heart_rate" | "rpe";
export type TargetUnit = "sec_per_km" | "sec_per_100m" | "watts" | "bpm" | "rpe_0_10";

export type StepTarget = {
  metric: TargetMetric;
  unit: TargetUnit;
  minimum: number;
  maximum: number;
};

export type WorkoutStep = {
  kind: StepKind;
  duration_sec?: number;
  distance_m?: number;
  target?: StepTarget;
};

export type StepGroup = { repetitions: number; steps: WorkoutStep[] };

export type Workout = {
  id: number;
  athlete_id: number;
  coach_id: number | null;
  title: string;
  description: string | null;
  scheduled_date: string;
  sport_type: Sport;
  status: "draft" | "published";
  version: number;
  block_id: number | null;
  steps: StepGroup[];
};

export type WorkoutInput = Omit<Workout, "id" | "athlete_id" | "coach_id" | "status" | "version">;

export type ApiProblem = {
  status: number;
  message: string;
  detail?: unknown;
};

export type OptionalFeatureState<T> =
  | { kind: "ready"; data: T }
  | { kind: "unavailable"; contract: string }
  | { kind: "error"; problem: ApiProblem };
