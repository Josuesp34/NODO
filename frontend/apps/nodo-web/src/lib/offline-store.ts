import type { Workout } from "./contracts";

export type CachedWorkouts = { userId: number; timezone: string; savedAt: string; expiresAt: string; workouts: Workout[] };
const prefix = "nodo.offline.";
const activeKey = `${prefix}active`;
export const offlineLifetimeMs = 24 * 60 * 60 * 1000;
const clearEvent = "nodo:offline-cleared";
const sessionEventKey = "nodo.session.invalidated";

export function invalidateOtherSessions() {
  clearOfflineData();
  window.dispatchEvent(new Event(clearEvent));
  try { window.localStorage.setItem(sessionEventKey, `${Date.now()}:${crypto.randomUUID()}`); } catch { /* Sin almacenamiento. */ }
}

export function saveWorkouts(userId: number, workouts: Workout[], timezone = "America/Mexico_City") {
  try {
    const now = Date.now();
    const copy: CachedWorkouts = { userId, timezone, savedAt: new Date(now).toISOString(), expiresAt: new Date(now + offlineLifetimeMs).toISOString(), workouts: workouts.filter((workout) => workout.athlete_id === userId && workout.status === "published").slice(0, 100) };
    window.localStorage.setItem(`${prefix}workouts.${userId}`, JSON.stringify(copy));
    window.localStorage.setItem(activeKey, String(userId));
  } catch { /* Un dispositivo sin almacenamiento sigue funcionando en línea. */ }
}

export function readWorkouts(userId: number): CachedWorkouts | null {
  try {
    const key = `${prefix}workouts.${userId}`;
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const copy = JSON.parse(raw) as CachedWorkouts;
    if (copy.userId !== userId || !Array.isArray(copy.workouts) || !copy.timezone || !Number.isFinite(Date.parse(copy.expiresAt)) || Date.parse(copy.expiresAt) <= Date.now()) {
      window.localStorage.removeItem(key);
      return null;
    }
    return { ...copy, workouts: copy.workouts.filter((workout) => workout.athlete_id === userId && workout.status === "published") };
  } catch { return null; }
}

export function readActiveWorkouts(): CachedWorkouts | null {
  try {
    const userId = Number(window.localStorage.getItem(activeKey));
    return Number.isInteger(userId) && userId > 0 ? readWorkouts(userId) : null;
  } catch { return null; }
}

export function clearOfflineData() {
  let hadCopy = false;
  try { const keys = Object.keys(window.localStorage).filter((key) => key.startsWith(prefix)); hadCopy = keys.length > 0; keys.forEach((key) => window.localStorage.removeItem(key)); } catch { /* Almacenamiento deshabilitado. */ }
  if (hadCopy) window.dispatchEvent(new Event(clearEvent));
  navigator.serviceWorker?.controller?.postMessage({ type: "CLEAR_AUTH_CACHE" });
}

export function observeOfflineInvalidation(invalidate: () => void) {
  const storage = (event: StorageEvent) => {
    if (event.key === sessionEventKey) { invalidate(); return; }
    if (event.key?.startsWith(prefix) && (event.newValue === null || (event.key === activeKey && event.oldValue !== event.newValue))) invalidate();
  };
  window.addEventListener(clearEvent, invalidate);
  window.addEventListener("storage", storage);
  return () => { window.removeEventListener(clearEvent, invalidate); window.removeEventListener("storage", storage); };
}
