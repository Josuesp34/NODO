export type UserRole = "coach" | "athlete";

export type Identity = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  timezone: string;
  role: UserRole;
  coach_id: number | null;
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
};

export type StepTarget = {
  metric: "pace" | "power" | "heart_rate" | "rpe";
  unit: "sec_per_km" | "sec_per_100m" | "watts" | "bpm" | "rpe_0_10";
  minimum: number;
  maximum: number;
};

export type WorkoutStep = {
  kind: "warmup" | "work" | "recovery" | "cooldown";
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
  sport_type: "running" | "cycling" | "swimming";
  status: "draft" | "published";
  version: number;
  block_id: number | null;
  steps: StepGroup[];
};

export class NodoApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "NodoApiError";
  }
}

type RequestOptions = Omit<RequestInit, "body" | "headers"> & { body?: unknown };

export class NodoApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string, private readonly token?: string) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
        ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => null) as { detail?: string } | null;
      throw new NodoApiError(response.status, payload?.detail ?? `NODO API ${response.status}`);
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }

  login(email: string, password: string) {
    return this.request<TokenPair>("/auth/login", { method: "POST", body: { email, password } });
  }

  refresh(refreshToken: string) {
    return this.request<TokenPair>("/auth/refresh", { method: "POST", body: { refresh_token: refreshToken } });
  }

  me() { return this.request<Identity>("/auth/me"); }
  logout() { return this.request<void>("/auth/logout", { method: "POST" }); }
  workouts(athleteId: number, start: string, end: string) {
    return this.request<Workout[]>(`/athletes/${athleteId}/workouts?start=${start}&end=${end}`);
  }
}
