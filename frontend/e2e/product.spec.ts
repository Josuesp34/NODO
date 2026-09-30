import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const credentials = JSON.parse(readFileSync(resolve(process.env.NODO_DEMO_CREDENTIALS ?? "../.local/nodo-demo/credentials.json"), "utf8")) as { password: string };
const apiURL = process.env.NODO_E2E_API_URL ?? "http://127.0.0.1:8800/api/v1";
const webURL = process.env.NODO_E2E_WEB_URL ?? "http://127.0.0.1:3300";

async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Correo", { exact: true }).fill(email);
  await page.getByLabel("Contraseña", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "Entrar a NODO" }).click();
  await expect(page).toHaveURL(/\/(coach|athlete\/today)$/, { timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Salir", exact: true })).toBeVisible();
  await expect(page.locator("h1")).toBeVisible();
}

test("coach y atleta leen la misma sesión publicada con cookies privadas", async ({ browser, request }) => {
  const coachContext = await browser.newContext({ baseURL: webURL });
  const athleteContext = await browser.newContext({ baseURL: webURL });
  const coach = await coachContext.newPage();
  const athlete = await athleteContext.newPage();
  await login(coach, "coach-demo@example.com");
  await coach.goto("/coach/athletes");
  await expect(coach.getByText("Atleta Demo", { exact: true }).first()).toBeVisible();
  await login(athlete, "athlete-demo@example.com");
  await athlete.goto("/athlete/today");
  await expect(athlete.getByText("Rodaje de demostración", { exact: true }).first()).toBeVisible();
  const cookies = await athleteContext.cookies();
  const sessionCookies = cookies.filter((cookie) => /nodo.*(access|refresh)/.test(cookie.name));
  expect(sessionCookies).toHaveLength(2);
  expect(sessionCookies.every((cookie) => cookie.httpOnly && cookie.sameSite === "Lax")).toBe(true);
  const clientState = await athlete.evaluate(() => ({
    cookies: document.cookie,
    local: Object.entries(localStorage),
    session: Object.entries(sessionStorage),
  }));
  for (const cookie of sessionCookies) {
    expect(JSON.stringify(clientState)).not.toContain(cookie.value);
  }
  const health = await request.get(apiURL.replace("/api/v1", "/health"));
  expect(health.ok()).toBe(true);
  await athlete.getByRole("button", { name: "Salir", exact: true }).click();
  await expect(athlete).toHaveURL(/\/$/);
  expect(await athlete.evaluate(() => Object.keys(localStorage).filter((key) => key.startsWith("nodo.offline")))).toEqual([]);
  await coachContext.close();
  await athleteContext.close();
});

test("la cuenta multirol cambia de módulo y la persona sin coach conserva su cuenta", async ({ page }) => {
  await login(page, "dual-demo@example.com");
  await page.getByRole("navigation", { name: "Cambiar módulo" }).getByRole("link", { name: "Atleta", exact: true }).click();
  await expect(page).toHaveURL(/\/athlete\/today/);
  await page.getByRole("navigation", { name: "Cambiar módulo" }).getByRole("link", { name: "Coach", exact: true }).click();
  await expect(page).toHaveURL(/\/coach$/);
  await page.getByRole("button", { name: "Salir", exact: true }).click();
  await login(page, "solo-demo@example.com");
  await expect(page.getByText("Hoy no hay una sesión publicada.", { exact: true })).toBeVisible();
  await page.goto("/athlete/check-in");
  await expect(page.locator("h1")).toBeVisible();
});

test("el BFF rechaza escrituras desde otro origen antes de la API", async ({ page }) => {
  await login(page, "athlete-demo@example.com");
  const response = await page.request.post("/api/session/logout", { headers: { Origin: "https://another-origin.example" } });
  expect(response.status()).toBe(403);
  const identity = await page.request.get("/api/session/me");
  expect(identity.ok()).toBe(true);
});

test("el plan guardado funciona sin red y se elimina al salir o cambiar de cuenta", async ({ page, context, browserName }) => {
  await login(page, "athlete-demo@example.com");
  await page.goto("/athlete/today");
  await expect(page.getByText("Rodaje de demostración", { exact: true }).first()).toBeVisible();
  await page.evaluate(() => navigator.serviceWorker.ready);
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);
  await context.setOffline(true);
  // WebKit 1.63 rejects even literal SW responses with offline emulation.
  // Its open-page offline state is still tested; Chromium also tests a full navigation.
  // https://github.com/microsoft/playwright/issues/42775
  if (browserName !== "webkit") await page.goto("/athlete/today");
  await expect(page.getByRole("heading", { name: "Tu plan sin conexión" })).toBeVisible();
  await expect(page.getByText("Rodaje de demostración", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Borrar copia de este dispositivo" }).click();
  await expect(page.getByText(/No hay una copia vigente/)).toBeVisible();
  await context.setOffline(false);
  await page.goto("/athlete/today");
  await page.getByRole("button", { name: "Salir", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await login(page, "solo-demo@example.com");
  await page.goto("/offline");
  await expect(page.getByText("Rodaje de demostración", { exact: true })).toHaveCount(0);
});



test("salir invalida el plan que estaba abierto en otra pestaña", async ({ page, context }) => {
  await login(page, "athlete-demo@example.com");
  const other = await context.newPage();
  await other.goto("/athlete/today");
  await expect(other.getByText("Rodaje de demostración", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Salir", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(other).toHaveURL(/\/login/);
  await expect(other.getByText("Rodaje de demostración", { exact: true })).toHaveCount(0);
  await other.goto("/offline");
  await expect(other.getByText(/No hay una copia vigente/)).toBeVisible();
});

test("la copia abierta vence mientras el dispositivo sigue sin red", async ({ page, context }) => {
  await login(page, "athlete-demo@example.com");
  await page.goto("/athlete/today");
  await expect(page.getByText("Rodaje de demostración", { exact: true }).first()).toBeVisible();
  await page.clock.install();
  await page.evaluate(() => {
    for (const key of Object.keys(localStorage).filter((item) => item.startsWith("nodo.offline.workouts."))) {
      const copy = JSON.parse(localStorage.getItem(key)!);
      copy.expiresAt = new Date(Date.now() + 60_000).toISOString();
      localStorage.setItem(key, JSON.stringify(copy));
    }
  });
  await page.goto("/offline");
  await expect(page.getByText("Rodaje de demostración", { exact: true }).first()).toBeVisible();
  await context.setOffline(true);
  await page.clock.fastForward(61_000);
  await expect(page.getByText(/No hay una copia vigente/)).toBeVisible();
  await expect(page.getByText("Rodaje de demostración", { exact: true })).toHaveCount(0);
});



test("historial, check-in, molestias y chat del atleta persisten en el servidor", async ({ page }) => {
  await login(page, "athlete-demo@example.com");
  await page.goto("/athlete/activities");
  await expect(page.getByRole("heading", { name: "Historial y comparación" })).toBeVisible();
  await expect(page.getByText(/manual_fit|FIT manual/).first()).toBeVisible();
  await page.goto("/athlete/check-in");
  await page.getByLabel("Nota opcional").fill("Check-in sintético del navegador");
  await page.getByRole("button", { name: "Guardar check-in" }).click();
  await expect(page.getByText(/Check-in guardado/)).toBeVisible();
  await page.goto("/athlete/complaints/new");
  await page.getByLabel("Zona corporal").fill("Molestia sintética E2E");
  await page.getByRole("button", { name: "Enviar reporte" }).click();
  await expect(page.getByText(/Reporte guardado/)).toBeVisible();
  await page.goto("/athlete/complaints");
  await expect(page.getByRole("heading", { name: /Molestia sintética E2E/ }).first()).toBeVisible();
  await page.goto("/athlete/assistant");
  await expect(page.getByText(/Modo simulado/)).toBeVisible();
  await page.getByLabel("Tu mensaje").fill("¿Qué tengo hoy?");
  await page.getByRole("button", { name: "Enviar", exact: true }).click();
  await expect(page.getByLabel("Historial del asistente").getByText("NODO", { exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole("combobox", { name: "Conversación", exact: true }).selectOption({ index: 1 });
  await expect(page.getByLabel("Historial del asistente").getByText("¿Qué tengo hoy?", { exact: true })).toBeVisible();
});


test.describe("transporte autorizado sin interceptación del service worker", () => {
  test.use({ serviceWorkers: "block" });
test("entrar en otra cuenta invalida la copia repoblada durante el login", async ({ page, context }) => {
  const nextAccount = await context.newPage();
  await nextAccount.goto("/login");
  await expect(nextAccount.getByLabel("Correo", { exact: true })).toBeVisible();
  await login(page, "athlete-demo@example.com");
  await expect(page.getByText("Rodaje de demostración", { exact: true }).first()).toBeVisible();
  let release!: () => void;
  let entered = false;
  const delayed = new Promise<void>((resolve) => { release = resolve; });
  await nextAccount.route("**/api/session/login", async (route) => {
    entered = true;
    await delayed;
    await route.continue();
  });
  await nextAccount.getByLabel("Correo", { exact: true }).fill("coach-demo@example.com");
  await nextAccount.getByLabel("Contraseña", { exact: true }).fill(credentials.password);
  await nextAccount.getByRole("button", { name: "Entrar a NODO" }).click();
  await expect.poll(() => entered).toBe(true);
  // The first tab may revalidate the old cookie while the new login is pending.
  await page.reload();
  await expect.poll(() => page.evaluate(() => Object.keys(localStorage).some((key) => key.startsWith("nodo.offline.workouts.")))).toBe(true);
  release();
  await expect(nextAccount).toHaveURL(/\/coach$/);
  await expect(page.getByText("Rodaje de demostración", { exact: true })).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => Object.keys(localStorage).filter((key) => key.startsWith("nodo.offline")))).toEqual([]);
  await page.goto("/offline");
  await expect(page.getByText(/No hay una copia vigente/)).toBeVisible();
});
test("una copia vencida o una denegación HTTP deja de mostrar el plan", async ({ page }) => {
  await login(page, "athlete-demo@example.com");
  await page.goto("/athlete/today");
  await expect(page.getByText("Rodaje de demostración", { exact: true }).first()).toBeVisible();
  await page.route("**/api/nodo/athletes/*/workouts?*", (route) => route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "CONSENT_REQUIRED" }) }));
  await page.goto("/athlete/today");
  await expect(page.getByRole("alert").filter({ hasText: "CONSENT_REQUIRED" })).toBeVisible();
  await expect(page.getByText("Rodaje de demostración", { exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => Object.keys(localStorage).filter((key) => key.startsWith("nodo.offline")))).toEqual([]);
  await page.unroute("**/api/nodo/athletes/*/workouts?*");
  await page.goto("/athlete/today");
  await expect(page.getByText("Rodaje de demostración", { exact: true }).first()).toBeVisible();
  await page.evaluate(() => {
    for (const key of Object.keys(localStorage).filter((item) => item.startsWith("nodo.offline.workouts."))) {
      const copy = JSON.parse(localStorage.getItem(key)!);
      copy.expiresAt = "2000-01-01T00:00:00Z";
      localStorage.setItem(key, JSON.stringify(copy));
    }
  });
  await page.goto("/offline");
  await expect(page.getByText(/No hay una copia vigente/)).toBeVisible();
  await expect(page.getByText("Rodaje de demostración", { exact: true })).toHaveCount(0);
});

test("una respuesta anterior al logout no restaura datos al cambiar de cuenta", async ({ page }) => {
  await login(page, "athlete-demo@example.com");
  let release!: () => void;
  let entered = false;
  const delayed = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/nodo/athletes/*/workouts?*", async (route) => {
    const response = await route.fetch();
    entered = true;
    await delayed;
    await route.fulfill({ response }).catch(() => undefined);
  });
  await page.goto("/athlete/week");
  await expect.poll(() => entered).toBe(true);
  await page.getByRole("button", { name: "Salir", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.unroute("**/api/nodo/athletes/*/workouts?*");
  await login(page, "solo-demo@example.com");
  release();
  await expect(page.getByText("Hoy no hay una sesión publicada.", { exact: true })).toBeVisible();
  await page.goto("/offline");
  await expect(page.getByText("Rodaje de demostración", { exact: true })).toHaveCount(0);
});
});
