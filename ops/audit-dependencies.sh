#!/usr/bin/env bash
set -euo pipefail

audit_python="${1:?Python aislado con pip-audit}"
audit_requirements="${2:?Resolución Python congelada antes de instalar herramientas}"
audit_reports="${3:?Directorio de reportes}"
test -s "$audit_requirements"
mkdir -p "$audit_reports"

# Run all three controls and preserve every failure, including registry/network failures.
audit_failed=0
if npm --prefix frontend audit --omit=dev --json > "$audit_reports/npm-runtime.json"; then
  :
else
  audit_failed=1
fi
if npm --prefix frontend audit --json > "$audit_reports/npm-total.json"; then
  :
else
  audit_failed=1
fi
# --no-deps is safe here only because pip already resolved and froze the complete tree.
if "$audit_python" -m pip_audit --strict --no-deps --disable-pip --requirement "$audit_requirements" --format json --output "$audit_reports/pip-resolved.json"; then
  :
else
  audit_failed=1
fi
if node ops/check-audit-reports.mjs "$audit_reports"; then
  :
else
  audit_failed=1
fi
exit "$audit_failed"
