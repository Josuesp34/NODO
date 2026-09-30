import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);
const source = (path) => readFile(new URL(path, root), "utf8");

test("la sesión usa cookies httpOnly y no expone tokens al cliente", async () => {
  const session = await source("src/lib/session-server.ts");
  const login = await source("src/app/(public)/login/page.tsx");
  assert.match(session, /httpOnly:\s*true/);
  assert.match(session, /sameSite:\s*"lax"/);
  assert.doesNotMatch(login, /localStorage\.setItem\([^)]*token/i);
  assert.doesNotMatch(login, /sessionStorage/);
});

test("el proxy bloquea endpoints de bootstrap y refresh", async () => {
  const proxy = await source("src/app/api/nodo/[...path]/route.ts");
  for (const route of ["auth/login", "auth/refresh", "auth/coaches", "auth/superusers"]) assert.match(proxy, new RegExp(route.replace("/", "\\/")));
});

test("la PWA declara manifest, service worker y fallback offline", async () => {
  const manifest = await source("src/app/manifest.ts");
  const worker = await source("public/sw.js");
  assert.match(manifest, /display:\s*"standalone"/);
  assert.match(worker, /\/offline/);
  assert.match(worker, /CLEAR_AUTH_CACHE/);
  assert.doesNotMatch(worker, /\/api\/.+cache\.put/s);
});

test("el editor conserva varias sesiones por día y expected_version", async () => {
  const planning = await source("src/components/planning-workspace.tsx");
  assert.match(planning, /Record<string, Workout\[\]>/);
  assert.match(planning, /expected_version/);
  assert.match(planning, /status === 409/);
});

test("la imagen de producción usa standalone, usuario no root y PORT 8080", async () => {
  const config = await source("next.config.ts");
  const dockerfile = await source("Dockerfile");
  assert.match(config, /output:\s*"standalone"/);
  assert.match(dockerfile, /PORT=8080/);
  assert.match(dockerfile, /USER nextjs/);
  assert.match(dockerfile, /apps\/nodo-web\/server\.js/);
});

test("el canal comercial no inventa una dirección de contacto", async () => {
  const landing = await source("src/app/(public)/page.tsx");
  const support = await source("src/app/(public)/support/page.tsx");
  assert.doesNotMatch(landing, /mailto:/);
  assert.match(support, /process\.env\.NODO_CONTACT_URL/);
  assert.match(support, /Canal comercial por configurar/);
});

test("la guía FIT es pública y la interfaz no presenta Intervals como conexión real", async () => {
  const guide = await source("src/app/(public)/guide/fit/page.tsx");
  const support = await source("src/app/(public)/support/page.tsx");
  const athlete = await source("src/components/athlete-features.tsx");
  assert.match(guide, /10 MiB/);
  assert.match(guide, /Intervals\.icu/);
  assert.match(support, /href="\/guide\/fit"/);
  assert.match(athlete, /Conexión real pendiente/);
  assert.match(athlete, /OAuth, sincronización ni webhooks/);
  assert.match(athlete, /href="\/guide\/fit"/);
  assert.match(athlete, /nodoRequest<Connection>\(connectionPath\)/);
  assert.doesNotMatch(athlete, /connect\("real"\)/);
});

test("los adapters de producto respetan los contratos autenticados actuales", async () => {
  const athlete = await source("src/components/athlete-features.tsx");
  const coach = await source("src/components/coach-features.tsx");
  const settings = await source("src/components/settings-workspaces.tsx");
  assert.match(athlete, /athletes\/\$\{identity\.id\}\/checkins\/\$\{form\.local_date\}/);
  assert.match(athlete, /athletes\/\$\{identity\.id\}\/activities\/fit/);
  assert.match(coach, /review-items\/\$\{item\.id\}\/decision/);
  const recommendations = await source("src/components/recommendations-workspace.tsx");
  const resources = await source("src/components/resources-workspace.tsx");
  assert.match(recommendations, /recommendations\/\$\{p\.id\}\/decision/);
  assert.match(recommendations, /nodoRequest<Proposal\[\]>\("recommendations"\)/);
  assert.match(resources, /nodoRequest<Template\[\]>\("templates"\)/);
  assert.match(resources, /nodoRequest<Group\[\]>\("groups"\)/);
  assert.match(settings, /nodoRequest<Consent\[\]>\("consents"\)/);
  assert.match(settings, /account\/export/);
  assert.match(settings, /ELIMINAR MI CUENTA/);
});

test("las capacidades granulares del backend se normalizan al módulo correcto", async () => {
  const contracts = await source("src/lib/contracts.ts");
  assert.match(contracts, /capability\.split\(":"/);
  assert.match(contracts, /scope === "coach"/);
  assert.match(contracts, /identity\.is_superuser/);
});
