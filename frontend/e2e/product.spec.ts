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
  await expect(page).toHaveURL(/\/(coach|athlete|app)/);
  await expect(page.getByRole("button", { name: "Salir", exact: true })).toBeVisible();
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

test("el plan guardado funciona sin red y se elimina al salir o cambiar de cuenta", async ({ page, context }) => {
  await login(page, "athlete-demo@example.com");
  await page.goto("/athlete/today");
  await expect(page.getByText("Rodaje de demostración", { exact: true }).first()).toBeVisible();
  await page.evaluate(() => navigator.serviceWorker.ready);
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);
  await context.setOffline(true);
  await page.goto("/athlete/today");
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

test("una copia vencida o una denegación HTTP deja de mostrar el plan", async ({ page }) => {
  await login(page, "athlete-demo@example.com");
  await page.goto("/athlete/today");
  await expect(page.getByText("Rodaje de demostración", { exact: true }).first()).toBeVisible();
  await page.route("**/api/nodo/athletes/*/workouts?*", (route) => route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "CONSENT_REQUIRED" }) }));
  await page.goto("/athlete/today");
  await expect(page.getByText("CONSENT_REQUIRED", { exact: true })).toBeVisible();
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
