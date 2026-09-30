import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import { createRequire } from "node:module";
import { webcrypto, createHash } from "node:crypto";

const require = createRequire(import.meta.url);
const { transform, loadBindings } = require("next/dist/build/swc");
await loadBindings();
const root = new URL("../", import.meta.url);

test("el service worker ignora texto privado y URLs externas del payload", async () => {
  const events = new Map(); const shown = []; const opened = [];
  const self = {
    addEventListener: (name, callback) => events.set(name, callback),
    location: { origin: "https://nodo.example" },
    registration: { showNotification: async (title, options) => shown.push({ title, options }) },
    clients: { matchAll: async () => [], openWindow: async (url) => opened.push(url) },
  };
  vm.runInNewContext(await readFile(new URL("public/sw.js", root), "utf8"), { self, URL });
  let operation;
  events.get("push")({ data: { json: () => ({ title: "Private athlete", body: "Private metric", url: "https://attacker.example", tag: "untrusted" }) }, waitUntil: (promise) => operation = promise });
  await operation;
  assert.equal(shown[0].title, "NODO");
  assert.doesNotMatch(JSON.stringify(shown), /Private athlete|Private metric|attacker/);
  events.get("notificationclick")({ notification: { close() {}, data: { url: "https://attacker.example" } }, waitUntil: (promise) => operation = promise });
  await operation;
  assert.deepEqual(opened, ["/app"]);
});

async function clientHarness({ permission = "granted", backendFails = false } = {}) {
  const effects = [];
  const subscription = { endpoint: "synthetic", toJSON: () => ({ endpoint: "synthetic" }), unsubscribe: async () => effects.push("browser-unsubscribe") };
  const registration = { pushManager: { getSubscription: async () => null, subscribe: async () => subscription }, getNotifications: async () => [{ close: () => effects.push("close-notification") }] };
  const exports = {};
  const source = await readFile(new URL("src/lib/push-client.ts", root), "utf8");
  const compiled = (await transform(source, { filename: "push-client.ts", jsc: { parser: { syntax: "typescript" }, target: "es2022" }, module: { type: "commonjs" } })).code;
  const context = {
    exports, module: { exports }, Uint8Array, ArrayBuffer, atob, TextEncoder, crypto: webcrypto,
    window: { isSecureContext: true, PushManager: {}, Notification: {} },
    navigator: { serviceWorker: { ready: Promise.resolve(registration) } },
    Notification: { requestPermission: async () => permission },
    require: () => ({ nodoRequest: async () => { effects.push("server"); if (backendFails) throw new Error("Synthetic failure"); return { id: 1 }; } }),
  };
  vm.runInNewContext(compiled, context);
  return { exports, effects, registration, subscription };
}

test("denegación de permiso no registra un dispositivo y falla de backend revierte el alta local", async () => {
  const denied = await clientHarness({ permission: "denied" });
  await assert.rejects(denied.exports.subscribeDevice("AA"), /permiso/);
  assert.deepEqual(denied.effects, []);
  const failed = await clientHarness({ backendFails: true });
  await assert.rejects(failed.exports.subscribeDevice("AA"), /Synthetic failure/);
  assert.deepEqual(failed.effects, ["server", "browser-unsubscribe"]);
});

test("la baja confirma servidor antes de limpiar dispositivo y avisos visibles", async () => {
  const client = await clientHarness();
  client.registration.pushManager.getSubscription = async () => client.subscription;
  await client.exports.unsubscribeDevice(1, createHash("sha256").update("synthetic").digest("hex"));
  assert.deepEqual(client.effects, ["server", "browser-unsubscribe", "close-notification"]);
});

test("revocar otro dispositivo conserva la suscripción de este navegador", async () => {
  const client = await clientHarness();
  client.registration.pushManager.getSubscription = async () => client.subscription;
  await client.exports.unsubscribeDevice(2, createHash("sha256").update("another-device").digest("hex"));
  assert.deepEqual(client.effects, ["server"]);
});
