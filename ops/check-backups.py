#!/usr/bin/env python3
"""Read existing Cloud SQL backup inventory; never creates/restores/deletes a backup."""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime


def evaluate(backups, now, max_age_hours=36):
    if not isinstance(backups, list):
        raise TypeError("inventory_contract")
    latest = []
    successful = []
    known_states = {
        "SUCCESSFUL",
        "RUNNING",
        "ENQUEUED",
        "SKIPPED",
        "FAILED",
        "OVERDUE",
        "DELETION_PENDING",
        "DELETION_FAILED",
        "DELETED",
        "SQL_BACKUP_RUN_STATUS_UNSPECIFIED",
    }
    for backup in backups:
        timestamp = (
            backup.get("endTime")
            or backup.get("startTime")
            or backup.get("windowStartTime")
        )
        if not timestamp:
            continue
        observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if observed.tzinfo is None or observed > now:
            raise ValueError("backup_time_invalid")
        status = backup.get("status")
        status = status if status in known_states else "UNKNOWN"
        latest.append((observed, status))
        if status == "SUCCESSFUL":
            successful.append(observed)
    last_status = max(latest, default=(None, "MISSING"), key=lambda row: row[0])[1]
    age = (now - max(successful)).total_seconds() / 3600 if successful else None
    healthy = (
        age is not None
        and age <= max_age_hours
        and last_status in {"SUCCESSFUL", "RUNNING", "ENQUEUED", "SKIPPED"}
    )
    return {
        "event": "backup_check",
        "healthy": healthy,
        "last_success_age_hours": round(age, 2) if age is not None else None,
        "latest_status": last_status,
    }


def main():
    try:
        project = os.environ["GCP_PROJECT_ID"]
        instance = os.environ["CLOUD_SQL_INSTANCE"]
        require_age = float(os.environ.get("BACKUP_MAX_AGE_HOURS", "36"))
        if require_age <= 0 or not project or not instance:
            raise ValueError("configuration_invalid")
        response = subprocess.run(
            [
                "gcloud",
                "sql",
                "backups",
                "list",
                "--project",
                project,
                "--instance",
                instance,
                "--limit",
                "100",
                "--format=json",
            ],
            check=True,
            capture_output=True,
            timeout=40,
        )
        if len(response.stdout) > 2 * 1024 * 1024:
            raise ValueError("inventory_limit")
        result = evaluate(json.loads(response.stdout), datetime.now(UTC), require_age)
    except Exception:  # noqa: BLE001 -- CLI boundary must redact provider errors and fail closed.
        result = {
            "event": "backup_check",
            "healthy": False,
            "check": "inventory_unavailable",
        }
    # IDs/locations/operator emails/raw provider errors are deliberately excluded.
    print(json.dumps(result))
    return 0 if result["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
