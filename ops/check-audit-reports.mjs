import { readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

export function assertAuditClean(report, ecosystem) {
  if (!report || typeof report !== "object" || report.error || report.errors) {
    throw new Error("El auditor devolvió un error o un reporte inválido.");
  }
  if (ecosystem === "npm") {
    const counts = report.metadata?.vulnerabilities;
    if (report.auditReportVersion !== 2 || !Number.isSafeInteger(report.metadata?.dependencies?.total) || report.metadata.dependencies.total < 1
      || !counts || !["info", "low", "moderate", "high", "critical", "total"].every((severity) => Number.isSafeInteger(counts[severity]) && counts[severity] >= 0)
      || !report.vulnerabilities || typeof report.vulnerabilities !== "object") {
      throw new Error("El reporte npm no confirma una auditoría completa.");
    }
    if (Object.values(counts).some((count) => count !== 0) || Object.keys(report.vulnerabilities).length !== 0) {
      throw new Error("npm encontró vulnerabilidades; el release queda bloqueado.");
    }
    return;
  }
  if (ecosystem !== "pip" || !Array.isArray(report.dependencies) || report.dependencies.length === 0) {
    throw new Error("El reporte Python no confirma una auditoría completa.");
  }
  for (const dependency of report.dependencies) {
    if (dependency.skip_reason || !dependency.name || !dependency.version || !Array.isArray(dependency.vulns)) {
      throw new Error("Python contiene una dependencia omitida o sin resultado de auditoría.");
    }
    if (dependency.vulns.length > 0) throw new Error("pip-audit encontró vulnerabilidades; el release queda bloqueado.");
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const directory = process.argv[2];
  let failed = false;
  for (const [filename, ecosystem] of [["npm-runtime.json", "npm"], ["npm-total.json", "npm"], ["pip-resolved.json", "pip"]]) {
    try {
      assertAuditClean(JSON.parse(await readFile(path.join(directory, filename), "utf8")), ecosystem);
      console.log(`${filename}: auditoría completa sin vulnerabilidades conocidas.`);
    } catch (error) {
      console.error(`${filename}: ${error.message}`);
      failed = true;
    }
  }
  if (failed) process.exitCode = 1;
}
