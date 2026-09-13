export type UserRole = "COACH" | "ATHLETE";

export type Workout = {
  id: number;
  athlete_id: number;
  title: string;
  scheduled_date: string;
  sport_type: string;
  status: "draft" | "published";
  version: number;
};

export class NodoApiClient {
  constructor(private readonly baseUrl: string, private readonly token?: string) {}

  async get<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      headers: this.token ? { Authorization: `Bearer ${this.token}` } : undefined,
    });
    if (!response.ok) throw new Error(`NODO API ${response.status}`);
    return response.json() as Promise<T>;
  }

  workouts(athleteId: number, start: string, end: string) {
    return this.get<Workout[]>(`/athletes/${athleteId}/workouts?start=${start}&end=${end}`);
  }
}
