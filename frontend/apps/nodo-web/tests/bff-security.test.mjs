import assert from "node:assert/strict";
import test from "node:test";
import { protectProxyRequest, protectSessionJson, protectSessionRequest } from "../src/lib/bff-security.ts";

const origin = "https://nodo.example";
const envNames = ["NODO_APP_ORIGIN", "NODO_BFF_SESSION_MAX_BYTES", "NODO_BFF_JSON_MAX_BYTES", "NODO_BFF_FIT_MAX_BYTES"];

function configure(t, values = {}) {
  for (const name of envNames) {
    const before = process.env[name];
    if (values[name] === undefined) delete process.env[name];
    else process.env[name] = String(values[name]);
    t.after(() => {
      if (before === undefined) delete process.env[name];
      else process.env[name] = before;
    });
  }
}

function request(body, headers = {}, method = "POST", url = `${origin}/api/session/login`) {
  return new Request(url, {
    method,
    headers: { Origin: origin, "Content-Type": "application/json", ...headers },
    ...(body === undefined ? {} : { body, duplex: "half" }),
  });
}

function streamedBody(chunks) {
  let index = 0;
  let cancelled = false;
  const stream = new ReadableStream({
    pull(controller) {
      if (index === chunks.length) controller.close();
      else controller.enqueue(chunks[index++]);
    },
    cancel() { cancelled = true; },
  }, { highWaterMark: 0 });
  return { stream, consumed: () => index, cancelled: () => cancelled };
}

test("login y activación aceptan JSON same-origin sin exponer el cuerpo al cliente", async (t) => {
  configure(t);
  const bodies = [];
  const handler = protectSessionJson(async (body) => { bodies.push(body); return Response.json({ ok: true }); });
  const response = await handler(request('{"email":"synthetic@example.test","password":"example"}', { "Sec-Fetch-Site": "same-origin" }));
  assert.equal(response.status, 200);
  assert.deepEqual(bodies, [{ email: "synthetic@example.test", password: "example" }]);
  assert.deepEqual(await response.json(), { ok: true });
});

test("sesión y logout rechazan Origin ausente o ajeno antes de leer o llamar al backend", async (t) => {
  configure(t);
  for (const createHandler of [protectSessionJson, protectSessionRequest]) {
    for (const value of [null, "https://other.example", "null", `${origin}/unexpected`, "http://nodo.example", `${origin}:444`]) {
      let calls = 0;
      const handler = createHandler(async () => { calls += 1; return Response.json({ ok: true }); });
      const req = request("{}");
      if (value === null) req.headers.delete("origin");
      else req.headers.set("origin", value);
      const response = await handler(req);
      assert.equal(response.status, 403, String(value));
      assert.equal(response.headers.get("cache-control"), "no-store");
      assert.equal(req.bodyUsed, false);
      assert.equal(calls, 0);
    }
  }
});

test("el proxy exige Origin para todas las escrituras aunque no lleven cuerpo", async (t) => {
  configure(t);
  let calls = 0;
  const handler = protectProxyRequest(async () => { calls += 1; return Response.json({ ok: true }); });
  for (const method of ["POST", "PUT", "PATCH", "DELETE"]) {
    const req = request(undefined, {}, method);
    req.headers.delete("origin");
    assert.equal((await handler("athletes/7/workouts/9", req)).status, 403);
    const crossOrigin = request(undefined, { Origin: "https://other.example" }, method);
    assert.equal((await handler("athletes/7/workouts/9", crossOrigin)).status, 403);
  }
  assert.equal(calls, 0);
});

test("Fetch Metadata de otro sitio no permite escritura aunque declare el Origin correcto", async (t) => {
  configure(t);
  let calls = 0;
  const handler = protectSessionJson(async () => { calls += 1; return Response.json({ ok: true }); });
  for (const site of ["same-site", "cross-site"]) {
    assert.equal((await handler(request("{}", { "Sec-Fetch-Site": site }))).status, 403);
  }
  assert.equal(calls, 0);
});

test("un origen canónico admite HTTPS tras un proxy sin confiar en headers de host", async (t) => {
  configure(t, { NODO_APP_ORIGIN: origin });
  let calls = 0;
  const handler = protectSessionJson(async () => { calls += 1; return Response.json({ ok: true }); });
  assert.equal((await handler(request("{}", { Host: "internal:8080", "X-Forwarded-Host": "evil.example" }, "POST", "http://internal:8080/api/session/login"))).status, 200);
  assert.equal((await handler(request("{}", { Origin: "https://evil.example", Host: "evil.example", "X-Forwarded-Host": "evil.example" }))).status, 403);
  assert.equal(calls, 1);
});

test("un origen o límite mal configurado falla cerrado y no llama al backend", async (t) => {
  configure(t, { NODO_APP_ORIGIN: `${origin}/login` });
  let calls = 0;
  const handler = protectSessionJson(async () => { calls += 1; return Response.json({ ok: true }); });
  assert.equal((await handler(request("{}"))).status, 503);
  process.env.NODO_APP_ORIGIN = origin;
  for (const limit of ["", "0", "-1", "1.5", "9007199254740992", "not-a-number"]) {
    process.env.NODO_BFF_SESSION_MAX_BYTES = limit;
    assert.equal((await handler(request("{}"))).status, 503);
  }
  assert.equal(calls, 0);
});

test("el proxy permite lecturas sin Origin y conserva ruta y headers necesarios", async (t) => {
  configure(t);
  const calls = [];
  const handler = protectProxyRequest(async (path, init) => { calls.push({ path, init }); return Response.json({ ok: true }); });
  const req = request(undefined, { Accept: "application/octet-stream" }, "GET");
  req.headers.delete("origin");
  assert.equal((await handler("account/export?format=json", req)).status, 200);
  assert.equal(calls[0].path, "account/export?format=json");
  assert.equal(calls[0].init.method, "GET");
  assert.equal(calls[0].init.headers.get("accept"), "application/octet-stream");
  assert.equal(calls[0].init.body, undefined);
});

test("la sesión corta un stream oversized sin Content-Length y no llama al backend", async (t) => {
  configure(t, { NODO_BFF_SESSION_MAX_BYTES: 32 });
  let calls = 0;
  const handler = protectSessionJson(async () => { calls += 1; return Response.json({ ok: true }); });
  const body = streamedBody([new Uint8Array(16), new Uint8Array(17), new Uint8Array(20)]);
  const response = await handler(request(body.stream));
  assert.equal(response.status, 413);
  assert.equal(body.consumed(), 2);
  assert.equal(body.cancelled(), true);
  assert.equal(calls, 0);
});

test("Content-Length mayor al límite rechaza y cancela antes de consumir bytes", async (t) => {
  configure(t, { NODO_BFF_JSON_MAX_BYTES: 32 });
  let calls = 0;
  const handler = protectProxyRequest(async () => { calls += 1; return Response.json({ ok: true }); });
  const body = streamedBody([new Uint8Array(20)]);
  const response = await handler("athletes/7/profile", request(body.stream, { "Content-Length": "33" }, "PUT"));
  assert.equal(response.status, 413);
  assert.equal(body.consumed(), 0);
  assert.equal(body.cancelled(), true);
  assert.equal(calls, 0);
});

test("Content-Length falso pequeño no elude el límite del stream", async (t) => {
  configure(t, { NODO_BFF_JSON_MAX_BYTES: 32 });
  let calls = 0;
  const handler = protectProxyRequest(async () => { calls += 1; return Response.json({ ok: true }); });
  const body = streamedBody([new Uint8Array(32), new Uint8Array(1), new Uint8Array(10)]);
  const response = await handler("athletes/7/profile", request(body.stream, { "Content-Length": "1" }, "PUT"));
  assert.equal(response.status, 413);
  assert.equal(body.consumed(), 2);
  assert.equal(body.cancelled(), true);
  assert.equal(calls, 0);
});

test("un tamaño falso dentro del límite o no numérico no se envía al backend", async (t) => {
  configure(t);
  let calls = 0;
  const handler = protectSessionJson(async () => { calls += 1; return Response.json({ ok: true }); });
  for (const declared of ["1", "3", "-1", "2.5", "garbage"]) {
    assert.equal((await handler(request("{}", { "Content-Length": declared }))).status, 400);
  }
  assert.equal(calls, 0);
});

test("un cuerpo ausente con Content-Length no cero también se rechaza", async (t) => {
  configure(t);
  let calls = 0;
  const handler = protectSessionRequest(async () => { calls += 1; return new Response(null, { status: 204 }); });
  assert.equal((await handler(request(undefined, { "Content-Length": "1" }))).status, 400);
  assert.equal(calls, 0);
});

test("la sesión tiene límite pequeño por defecto y JSON inválido devuelve 400 sin backend", async (t) => {
  configure(t);
  let calls = 0;
  const handler = protectSessionJson(async () => { calls += 1; return Response.json({ ok: true }); });
  assert.equal((await handler(request('{"password":"' + "x".repeat(16 * 1024) + '"}'))).status, 413);
  assert.equal((await handler(request("not-json"))).status, 400);
  assert.equal(calls, 0);
});

test("logout también limita cuerpo, pero admite el POST vacío legítimo", async (t) => {
  configure(t, { NODO_BFF_SESSION_MAX_BYTES: 4 });
  let calls = 0;
  const handler = protectSessionRequest(async () => { calls += 1; return new Response(null, { status: 204 }); });
  assert.equal((await handler(request("12345"))).status, 413);
  assert.equal(calls, 0);
  assert.equal((await handler(request(undefined))).status, 204);
  assert.equal(calls, 1);
});

test("escritura acotada conserva bytes exactos, Content-Type y ruta del proxy", async (t) => {
  configure(t, { NODO_BFF_JSON_MAX_BYTES: 32 });
  const calls = [];
  const handler = protectProxyRequest(async (path, init) => { calls.push({ path, init }); return Response.json({ saved: true }); });
  const input = '{"expected_version":3}';
  assert.equal((await handler("athletes/7/workouts/9", request(input, { "Content-Length": String(Buffer.byteLength(input)) }, "PUT"))).status, 200);
  assert.equal(new TextDecoder().decode(calls[0].init.body), input);
  assert.equal(calls[0].init.headers.get("content-type"), "application/json");
  assert.equal(calls[0].init.redirect, "manual");
  assert.equal(calls[0].path, "athletes/7/workouts/9");
});

test("FIT de 10 MiB y multipart caben; oversized sin tamaño no llega al backend", async (t) => {
  configure(t);
  const calls = [];
  const handler = protectProxyRequest(async (path, init) => { calls.push({ path, init }); return Response.json({ imported: true }); });
  const framing = new TextEncoder().encode('--boundary\r\nContent-Disposition: form-data; name="file"; filename="synthetic.fit"\r\nContent-Type: application/octet-stream\r\n\r\n');
  const footer = new TextEncoder().encode("\r\n--boundary--\r\n");
  const file = new Uint8Array(10 * 1024 * 1024);
  const body = streamedBody([framing, file, footer]);
  const headers = { "Content-Type": "multipart/form-data; boundary=boundary" };
  assert.equal((await handler("athletes/7/activities/fit", request(body.stream, headers))).status, 200);
  assert.equal(calls[0].init.body.byteLength, framing.byteLength + file.byteLength + footer.byteLength);
  const tooLarge = streamedBody([new Uint8Array(10 * 1024 * 1024), new Uint8Array(64 * 1024 + 1)]);
  assert.equal((await handler("athletes/7/activities/fit", request(tooLarge.stream, headers))).status, 413);
  assert.equal(tooLarge.cancelled(), true);
  assert.equal(calls.length, 1);
});

test("JSON y multipart en otras rutas no reciben el límite ampliado de FIT", async (t) => {
  configure(t);
  let calls = 0;
  const handler = protectProxyRequest(async () => { calls += 1; return Response.json({ ok: true }); });
  const oversized = new Uint8Array(1024 * 1024 + 1);
  assert.equal((await handler("athletes/7/activities/fit", request(oversized))).status, 413);
  assert.equal((await handler("athletes/7/profile", request(oversized, { "Content-Type": "multipart/form-data; boundary=boundary" }))).status, 413);
  assert.equal(calls, 0);
});

test("FIT permite configurar el límite del archivo y mantiene overhead acotado", async (t) => {
  configure(t, { NODO_BFF_FIT_MAX_BYTES: 8 });
  let calls = 0;
  const handler = protectProxyRequest(async () => { calls += 1; return Response.json({ ok: true }); });
  const headers = { "Content-Type": "multipart/form-data; boundary=boundary" };
  assert.equal((await handler("athletes/7/activities/fit", request(new Uint8Array(64 * 1024 + 8), headers))).status, 200);
  assert.equal((await handler("athletes/7/activities/fit", request(new Uint8Array(64 * 1024 + 9), headers))).status, 413);
  assert.equal(calls, 1);
});
