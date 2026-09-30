import { nodoRequest } from "./api";

export function pushSupported() {
  return window.isSecureContext && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function applicationServerKey(value: string): ArrayBuffer {
  const decoded = atob(value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - value.length % 4) % 4));
  const buffer = new ArrayBuffer(decoded.length);
  const bytes = new Uint8Array(buffer);
  for (let index = 0; index < decoded.length; index++) bytes[index] = decoded.charCodeAt(index);
  return buffer;
}

export async function subscribeDevice(publicKey: string) {
  if (!pushSupported()) throw new Error("Push requiere HTTPS y un navegador compatible. En iPhone, abre la PWA instalada desde Inicio.");
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("No se autorizó el permiso. Puedes cambiarlo desde los ajustes del navegador.");
  const registration = await navigator.serviceWorker.ready;
  const existing = await registration.pushManager.getSubscription();
  const subscription = existing ?? await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: applicationServerKey(publicKey) });
  try {
    return await nodoRequest<{ id: number }>("push-subscriptions", { method: "POST", body: subscription.toJSON() });
  } catch (error) {
    if (!existing) await subscription.unsubscribe().catch(() => undefined);
    throw error;
  }
}

export async function unsubscribeDevice(subscriptionId: number, endpointHash: string) {
  // Server withdrawal happens first, so an offline/browser failure cannot keep delivery active.
  await nodoRequest(`push-subscriptions/${subscriptionId}`, { method: "DELETE" });
  if ("serviceWorker" in navigator) {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    if (!subscription) return;
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(subscription.endpoint));
    const localHash = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
    // Revoking another device must not unsubscribe this browser.
    if (localHash !== endpointHash) return;
    await subscription?.unsubscribe();
    for (const notification of await registration.getNotifications()) notification.close();
  }
}
