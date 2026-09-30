import assert from "node:assert/strict";
import test from "node:test";
import { createBackendFetch, fetchWithRotatingSession } from "../src/lib/backend-transport.ts";

const pair = { access_token: "new-access", refresh_token: "new-refresh", expires_in: 1800 };

test("local no consulta metadata y conserva la ruta versionada", async () => {
  const calls = [];
  const backend = createBackendFetch("http://localhost:8000/api/v1/", "", async (url, init) => {
    calls.push({ url: String(url), init });
    return Response.json({ ok: true });
  });
  await backend("/auth/me", { headers: { Authorization: "Bearer user-session" } });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "http://localhost:8000/api/v1/auth/me");
  assert.equal(calls[0].init.headers.get("Authorization"), "Bearer user-session");
  assert.equal(calls[0].init.headers.get("X-Serverless-Authorization"), null);
  assert.equal(calls[0].init.cache, "no-store");
});

test("Cloud Run mantiene la sesión NODO y añade identidad con audiencia raíz", async () => {
  const calls = [];
  const token = `header.${Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 })).toString("base64url")}.signature`;
  const audience = "https://api-example.run.app";
  const backend = createBackendFetch(`${audience}/api/v1`, audience, async (url, init) => {
    calls.push({ url: String(url), init });
    return String(url).includes("metadata.google.internal") ? new Response(token) : Response.json({ ok: true });
  });
  await backend("auth/me", { headers: { Authorization: "Bearer user-session" } });
  await backend("auth/identity");
  assert.equal(calls.length, 3);
  assert.equal(new URL(calls[0].url).searchParams.get("audience"), audience);
  assert.equal(calls[0].init.headers["Metadata-Flavor"], "Google");
  assert.equal(calls[1].url, `${audience}/api/v1/auth/me`);
  assert.equal(calls[1].init.headers.get("Authorization"), "Bearer user-session");
  assert.equal(calls[1].init.headers.get("X-Serverless-Authorization"), `Bearer ${token}`);
  assert.equal(calls[2].init.headers.get("X-Serverless-Authorization"), `Bearer ${token}`);
});

test("una falla de identidad no envía una petición anónima a la API", async () => {
  let calls = 0;
  const backend = createBackendFetch("https://api-example.run.app/api/v1", "https://api-example.run.app", async () => {
    calls += 1;
    return new Response(null, { status: 503 });
  });
  await assert.rejects(backend("auth/me"), /identidad de Cloud Run/);
  assert.equal(calls, 1);
});

test("cookie access expirada renueva antes de consultar y devuelve cookies rotadas", async () => {
  const calls = [];
  const result = await fetchWithRotatingSession("auth/me", { method: "GET" }, { refresh: "valid-refresh" }, async (path, init) => {
    calls.push({ path, init });
    return Response.json(path === "auth/refresh" ? pair : { id: 7 });
  });
  assert.deepEqual(calls.map((call) => call.path), ["auth/refresh", "auth/me"]);
  assert.deepEqual(JSON.parse(calls[0].init.body), { refresh_token: "valid-refresh" });
  assert.equal(calls[1].init.headers.get("Authorization"), "Bearer new-access");
  assert.deepEqual(result.rotated, pair);
  assert.deepEqual(await result.response.json(), { id: 7 });
});

test("401 reintenta una vez y conserva exactamente el cuerpo de escritura", async () => {
  const calls = [];
  const body = new TextEncoder().encode('{"expected_version":3}').buffer;
  const result = await fetchWithRotatingSession("workouts/5", { method: "PUT", body }, { access: "old-access", refresh: "valid-refresh" }, async (path, init) => {
    calls.push({ path, init });
    if (path === "auth/refresh") return Response.json(pair);
    return calls.length === 1 ? new Response(null, { status: 401 }) : Response.json({ saved: true });
  });
  assert.equal(result.response.status, 200);
  assert.deepEqual(calls.map((call) => call.path), ["workouts/5", "auth/refresh", "workouts/5"]);
  assert.equal(calls[0].init.body, body);
  assert.equal(calls[2].init.body, body);
  assert.equal(calls[2].init.method, "PUT");
});

test("refresh inválido corta la sesión sin consultar el recurso protegido", async () => {
  const calls = [];
  const result = await fetchWithRotatingSession("auth/me", {}, { refresh: "revoked-refresh" }, async (path) => {
    calls.push(path);
    return new Response(null, { status: 401 });
  });
  assert.equal(result.response.status, 401);
  assert.deepEqual(calls, ["auth/refresh"]);
  assert.equal(result.rotated, undefined);
});

test("403 no provoca renovación ni repetición de una escritura", async () => {
  let calls = 0;
  const result = await fetchWithRotatingSession("athletes/99", { method: "DELETE" }, { access: "own-access", refresh: "valid-refresh" }, async () => {
    calls += 1;
    return new Response(null, { status: 403 });
  });
  assert.equal(result.response.status, 403);
  assert.equal(calls, 1);
});
