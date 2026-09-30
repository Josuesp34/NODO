import type { Workout } from "./contracts";

type CachedWorkouts = { savedAt: string; workouts: Workout[] };
const prefix = "nodo.offline.workouts";

export function saveWorkouts(userId: number, workouts: Workout[]) {
  window.localStorage.setItem(`${prefix}.${userId}`, JSON.stringify({ savedAt: new Date().toISOString(), workouts }));
}

export function readWorkouts(userId: number): CachedWorkouts | null {
  const raw = window.localStorage.getItem(`${prefix}.${userId}`);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as CachedWorkouts;
  } catch {
    window.localStorage.removeItem(`${prefix}.${userId}`);
    return null;
  }
}

export function clearOfflineData() {
  Object.keys(window.localStorage)
    .filter((key) => key.startsWith(prefix))
    .forEach((key) => window.localStorage.removeItem(key));
  void navigator.serviceWorker?.controller?.postMessage({ type: "CLEAR_AUTH_CACHE" });
}
