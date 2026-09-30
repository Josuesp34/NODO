import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { createBackendFetch, fetchWithRotatingSession, type TokenPair } from "@/lib/backend-transport";
import { protectProxyRequest } from "@/lib/bff-security";

const apiUrl = (process.env.NODO_API_URL ?? "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");
const cookieBase = process.env.SESSION_COOKIE_NAME ?? "nodo_session";
const accessCookie = `${cookieBase}_access`;
const refreshCookie = `${cookieBase}_refresh`;
const secure = process.env.SESSION_COOKIE_SECURE === "true" || process.env.NODE_ENV === "production";

const cookieOptions = {
  httpOnly: true,
  secure,
  sameSite: "lax" as const,
  path: "/",
};

export const backendFetch = createBackendFetch(apiUrl, process.env.NODO_CLOUD_RUN_AUDIENCE);

function setSession(response: NextResponse, pair: TokenPair) {
  response.cookies.set(accessCookie, pair.access_token, {
    ...cookieOptions,
    maxAge: pair.expires_in ?? 900,
  });
  response.cookies.set(refreshCookie, pair.refresh_token, {
    ...cookieOptions,
    maxAge: 60 * 60 * 24 * 14,
  });
}

export function clearSession(response: NextResponse) {
  response.cookies.set(accessCookie, "", { ...cookieOptions, maxAge: 0 });
  response.cookies.set(refreshCookie, "", { ...cookieOptions, maxAge: 0 });
}

export async function establishSession(authPath: string, body: unknown) {
  const tokenResponse = await backendFetch(authPath, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!tokenResponse.ok) return passThrough(tokenResponse);

  const pair = (await tokenResponse.json()) as TokenPair;
  const meResponse = await backendFetch("auth/me", {
    headers: { Accept: "application/json", Authorization: `Bearer ${pair.access_token}` },
  });
  if (!meResponse.ok) return passThrough(meResponse);

  const response = NextResponse.json({ user: await meResponse.json() });
  setSession(response, pair);
  response.headers.set("Cache-Control", "no-store");
  return response;
}

export async function currentIdentity() {
  return forwardAuthenticated("auth/me", { method: "GET", headers: { Accept: "application/json" } });
}

async function forwardAuthenticated(path: string, init: RequestInit) {
  const jar = await cookies();
  const { response, rotated } = await fetchWithRotatingSession(path, init, {
    access: jar.get(accessCookie)?.value,
    refresh: jar.get(refreshCookie)?.value,
  }, backendFetch);
  const forwarded = await passThrough(response);
  if (rotated) setSession(forwarded, rotated);
  if (response.status === 401) clearSession(forwarded);
  return forwarded;
}

export const authenticatedProxy = protectProxyRequest(forwardAuthenticated);

export async function logoutSession() {
  const jar = await cookies();
  await fetchWithRotatingSession("auth/logout", { method: "POST" }, {
    access: jar.get(accessCookie)?.value,
    refresh: jar.get(refreshCookie)?.value,
  }, backendFetch).catch(() => undefined);
  const response = new NextResponse(null, { status: 204 });
  clearSession(response);
  response.headers.set("Clear-Site-Data", '"cache", "storage"');
  return response;
}

export async function passThrough(response: Response) {
  const payload = response.status === 204 ? null : await response.arrayBuffer();
  const forwarded = new NextResponse(payload, { status: response.status });
  const contentType = response.headers.get("content-type");
  if (contentType) forwarded.headers.set("Content-Type", contentType);
  forwarded.headers.set("Cache-Control", "no-store");
  return forwarded;
}
