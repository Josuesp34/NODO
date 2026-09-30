import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { assertAuditClean } from "../check-audit-reports.mjs";

const cleanNpm = () => ({ auditReportVersion: 2, metadata: { vulnerabilities: { info: 0, low: 0, moderate: 0, high: 0, critical: 0, total: 0 }, dependencies: { total: 1 } }, vulnerabilities: {} });
const cleanPip = () => ({ dependencies: [{ name: "synthetic-package", version: "1.0.0", vulns: [] }], fixes: [] });
const root = path.resolve(import.meta.dirname, "../..");

test("los reportes completos sin findings son aceptados", () => {
  assert.doesNotThrow(() => assertAuditClean(cleanNpm(), "npm"));
  assert.doesNotThrow(() => assertAuditClean(cleanPip(), "pip"));
});

test("npm bloquea vulnerabilidades de cualquier severidad y errores de servicio", () => {
  for (const severity of ["info", "low", "moderate", "high", "critical"]) {
    const report = cleanNpm();
    report.metadata.vulnerabilities[severity] = 1;
    report.metadata.vulnerabilities.total = 1;
    assert.throws(() => assertAuditClean(report, "npm"), /vulnerabilidades/);
  }
  assert.throws(() => assertAuditClean({ error: { code: "ECONNRESET" } }, "npm"), /error/);
  assert.throws(() => assertAuditClean({ metadata: { vulnerabilities: {} } }, "npm"), /completa/);
  const inconsistent = cleanNpm();
  inconsistent.vulnerabilities.example = { severity: "high" };
  assert.throws(() => assertAuditClean(inconsistent, "npm"), /vulnerabilidades/);
  inconsistent.vulnerabilities = {};
  inconsistent.metadata.vulnerabilities.low = 1;
  assert.throws(() => assertAuditClean(inconsistent, "npm"), /vulnerabilidades/);
});

test("pip bloquea findings, paquetes omitidos, árboles vacíos y resultados incompletos", () => {
  for (const dependency of [
    { name: "example", version: "1.0", vulns: [{ id: "GHSA-synthetic" }] },
    { name: "example", skip_reason: "package not found" },
    { name: "example", version: "1.0" },
  ]) assert.throws(() => assertAuditClean({ dependencies: [dependency] }, "pip"));
  assert.throws(() => assertAuditClean({ dependencies: [] }, "pip"), /completa/);
  assert.throws(() => assertAuditClean({ errors: ["timeout"] }, "pip"), /error/);
});

test("el runner preserva fallos y ejecuta los tres escaneos sin omitir paquetes", async (t) => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "nodo-audit-test-"));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const bins = path.join(directory, "bin");
  await mkdir(bins);
  const trace = path.join(directory, "calls.txt");
  const frozen = path.join(directory, "resolved.txt");
  await writeFile(frozen, "synthetic-package==1.0.0\n");
  await writeFile(path.join(bins, "npm"), `#!/usr/bin/env bash
printf '%s\\n' "npm $*" >> "$AUDIT_TEST_TRACE"
printf '%s\\n' "$AUDIT_TEST_NPM_REPORT"
exit "$AUDIT_TEST_NPM_EXIT"
`, { mode: 0o755 });
  const python = path.join(bins, "python-audit");
  await writeFile(python, `#!/usr/bin/env bash
printf '%s\\n' "python $*" >> "$AUDIT_TEST_TRACE"
while [[ "$1" != "--output" ]]; do shift; done
printf '%s\\n' "$AUDIT_TEST_PIP_REPORT" > "$2"
exit "$AUDIT_TEST_PIP_EXIT"
`, { mode: 0o755 });
  for (const scenario of [
    { npmExit: 0, pipExit: 0, npm: cleanNpm(), pip: cleanPip(), expected: 0 },
    { npmExit: 1, pipExit: 0, npm: cleanNpm(), pip: cleanPip(), expected: 1 },
    { npmExit: 0, pipExit: 2, npm: cleanNpm(), pip: cleanPip(), expected: 1 },
    { npmExit: 1, pipExit: 0, npm: { error: { code: "ETIMEDOUT" } }, pip: cleanPip(), expected: 1 },
    { npmExit: 0, pipExit: 0, npm: cleanNpm(), pip: { dependencies: [{ name: "example", skip_reason: "unavailable" }] }, expected: 1 },
  ]) {
    await writeFile(trace, "");
    const reports = path.join(directory, "reports");
    const result = spawnSync("bash", ["ops/audit-dependencies.sh", python, frozen, reports], {
      cwd: root,
      encoding: "utf8",
      env: { ...process.env, PATH: `${bins}:${process.env.PATH}`, AUDIT_TEST_TRACE: trace,
        AUDIT_TEST_NPM_EXIT: String(scenario.npmExit), AUDIT_TEST_PIP_EXIT: String(scenario.pipExit),
        AUDIT_TEST_NPM_REPORT: JSON.stringify(scenario.npm), AUDIT_TEST_PIP_REPORT: JSON.stringify(scenario.pip) },
    });
    assert.equal(result.status, scenario.expected, result.stdout + result.stderr);
    const calls = (await readFile(trace, "utf8")).trim().split("\n");
    assert.equal(calls.length, 3);
    assert.match(calls[0], /audit --omit=dev --json/);
    assert.match(calls[1], /audit --json$/);
    assert.match(calls[2], /pip_audit --strict --no-deps --disable-pip --requirement/);
    assert.match(calls[2], new RegExp(frozen));
    assert.doesNotMatch(calls.join("\n"), /ignore-vuln|audit-level|--fix/);
  }
});
