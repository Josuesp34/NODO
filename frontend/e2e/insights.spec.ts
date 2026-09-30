import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// These cases intercept HTTP responses; offline/SW behavior is covered in product.spec.ts.
test.use({ serviceWorkers: "block" });

const credentials = JSON.parse(
  readFileSync(
    resolve(
      process.env.NODO_DEMO_CREDENTIALS ??
        "../.local/nodo-demo/credentials.json",
    ),
    "utf8",
  ),
) as { password: string };
const apiURL = process.env.NODO_E2E_API_URL ?? "http://127.0.0.1:8800/api/v1";
if (!["localhost", "127.0.0.1"].includes(new URL(apiURL).hostname))
  throw new Error("Insights E2E requires the local synthetic demo API");
async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Correo", { exact: true }).fill(email);
  await page
    .getByLabel("Contraseña", { exact: true })
    .fill(credentials.password);
  await page.getByRole("button", { name: "Entrar a NODO" }).click();
  await expect(page).toHaveURL(/\/(admin\/operations|coach|athlete\/today)$/, { timeout: 20_000 });
  await expect(
    page.getByRole("button", { name: "Salir", exact: true }),
  ).toBeVisible();
}

test("coach compara supuestos de carga y conserva el calendario", async ({
  page,
  request,
}) => {
  const auth = await request.post(`${apiURL}/auth/login`, {
    data: { email: "coach-demo@example.com", password: credentials.password },
  });
  expect(auth.ok()).toBe(true);
  const headers = {
    Authorization: `Bearer ${(await auth.json()).access_token}`,
  };
  const athletes = await request.get(`${apiURL}/auth/athletes`, { headers });
  const athlete = (await athletes.json()).find(
    (item: { email: string }) => item.email === "athlete-demo@example.com",
  );
  expect(athlete).toBeTruthy();
  const root = `${apiURL}/athletes/${athlete.id}`;
  const now = new Date();
  now.setUTCDate(now.getUTCDate() + 10);
  const day = now.toISOString().slice(0, 10);
  const created = await request.post(`${root}/competitions`, {
    headers,
    data: {
      name: `Synthetic scenario ${test.info().project.name}-${Date.now()}`,
      competition_date: day,
      discipline: "running",
      priority: "A",
    },
  });
  expect(created.status()).toBe(201);
  const competition = await created.json();
  try {
    const sessions = await (
      await request.get(`${root}/workouts?start=${day}&end=${day}`, { headers })
    ).json();
    await login(page, "coach-demo@example.com");
    await page.goto(`/coach/athletes/${athlete.id}/scenarios`);
    await expect(
      page.getByRole("heading", {
        name: "Comparar cargas hasta una competencia",
      }),
    ).toBeVisible();
    await page
      .getByRole("combobox", { name: /^Competencia/ })
      .selectOption(String(competition.id));
    await page.getByLabel("Introducir un estado inicial como supuesto").check();
    await page.getByLabel("CTL al cierre del día anterior").fill("42");
    await page.getByLabel("ATL al cierre del día anterior").fill("7");
    await page
      .getByLabel("Fuente o explicación de este supuesto")
      .fill("Estado sintético introducido por el coach");
    await page.getByLabel("Carga repetida cada día").nth(0).fill("0");
    await page
      .getByRole("button", { name: "Aplicar a estos días" })
      .nth(0)
      .click();
    await page.getByLabel("Carga repetida cada día").nth(1).fill("50");
    await page
      .getByRole("button", { name: "Aplicar a estos días" })
      .nth(1)
      .click();
    await page
      .getByRole("button", { name: "Comparar alternativas", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: /^Comparación · TRIMP/ }),
    ).toBeVisible();
    await expect(
      page.getByText(
        "No modifica ni publica sesiones. La revisión y cualquier cambio del calendario requieren otra acción.",
        { exact: true },
      ),
    ).toHaveCount(2);
    await expect(
      page
        .getByText("Estado sintético introducido por el coach", {
          exact: false,
        })
        .first(),
    ).toBeVisible();
    expect(
      await (
        await request.get(`${root}/workouts?start=${day}&end=${day}`, {
          headers,
        })
      ).json(),
    ).toEqual(sessions);
    await page.getByLabel("Nombre de alternativa 1").fill("Hipótesis revisada");
    await expect(
      page.getByRole("heading", { name: /^Comparación/ }),
    ).toHaveCount(0);
    let arrive!: () => void;
    let release!: () => void;
    let completed!: () => void;
    const arrived = new Promise<void>((resolve) => {
      arrive = resolve;
    });
    const released = new Promise<void>((resolve) => {
      release = resolve;
    });
    const finished = new Promise<void>((resolve) => {
      completed = resolve;
    });
    await page.route("**/scenarios", async (route) => {
      const response = await route.fetch();
      arrive();
      await released;
      try {
        await route.fulfill({ response });
      } catch {
        /* The edited form aborts the old browser request. */
      }
      completed();
    });
    await page
      .getByRole("button", { name: "Comparar alternativas", exact: true })
      .click();
    await arrived;
    await page
      .getByLabel("Nombre de alternativa 1")
      .fill("Hipótesis posterior");
    release();
    await finished;
    await expect(
      page.getByRole("heading", { name: /^Comparación/ }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Comparar alternativas", exact: true }),
    ).toBeEnabled();
  } finally {
    expect(
      (
        await request.delete(
          `${root}/competitions/${competition.id}?expected_version=${competition.version}`,
          { headers },
        )
      ).status(),
    ).toBe(204);
  }
});

test("administrador ve estimaciones y atleta ve sólo su uso", async ({
  page,
}) => {
  await login(page, "admin-demo@example.com");
  await page.goto("/settings/ai-costs");
  await expect(
    page.getByRole("heading", {
      name: "Uso y costos estimados de IA",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Presupuestos configurados y uso conservador",
    }),
  ).toBeVisible();
  await expect(page.getByText(/no son facturas del proveedor/)).toBeVisible();
  await page.getByRole("button", { name: "Salir", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await login(page, "athlete-demo@example.com");
  await page.goto("/settings/ai-costs");
  await expect(
    page.getByRole("heading", { name: "Mi uso de IA", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Mi cuenta", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Por cuenta de atleta o coach",
      exact: true,
    }),
  ).toHaveCount(0);
});
