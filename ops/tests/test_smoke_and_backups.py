import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


def load(name, path):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parents[1] / path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


smoke = load("smoke", "smoke-authenticated.py")
backups = load("backups", "check-backups.py")


class SmokeContract(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "alembic_revisions": ["0009_operations"],
            "worker_recent": True,
            "stale_running_count": 0,
            "queue": [{"kind": "send_resend_email", "status": "completed", "count": 1}],
        }
        self.logout_count = 0
        self.operation_status = 200
        self.athlete_id = 2
        self.login_token = False
        test = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, status, payload=None):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                if self.path == "/api/session/login":
                    self.send_header(
                        "Set-Cookie",
                        "nodo_session_access=synthetic-cookie; Path=/; HttpOnly; SameSite=Lax",
                    )
                self.end_headers()
                if payload is not None:
                    self.wfile.write(json.dumps(payload).encode())

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                self.server.origin_seen = self.headers.get("Origin")
                if self.path.endswith("/logout"):
                    test.logout_count += 1
                    self.reply(204)
                else:
                    self.reply(
                        200,
                        {"access_token": "forbidden-secret"}
                        if test.login_token
                        else {"user": {"id": 1}},
                    )

            def do_GET(self):
                if self.path == "/health":
                    if (
                        self.headers.get("X-Serverless-Authorization")
                        != "Bearer synthetic-iam"
                    ):
                        self.reply(403, {"detail": "Do not print synthetic-token"})
                    else:
                        self.reply(200, {"status": "ok"})
                elif (
                    self.headers.get("Cookie") != "nodo_session_access=synthetic-cookie"
                ):
                    self.reply(401)
                elif self.path.endswith("/me"):
                    self.reply(200, {"id": 1})
                elif self.path.endswith("/operations"):
                    self.reply(test.operation_status, test.payload)
                elif "/workouts?" in self.path:
                    self.reply(
                        200, [{"athlete_id": test.athlete_id, "status": "published"}]
                    )
                else:
                    self.reply(200, [])

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.env = {
            "SMOKE_ALLOW_LOOPBACK": "true",
            "SMOKE_PWA_URL": f"http://127.0.0.1:{self.server.server_port}",
            "SMOKE_API_URL": f"http://127.0.0.1:{self.server.server_port}",
            "SMOKE_API_ID_TOKEN": "synthetic-iam",
            "SMOKE_ADMIN_EMAIL": "synthetic-admin@example.com",
            "SMOKE_ADMIN_PASSWORD": "synthetic-password",
            "SMOKE_EXPECTED_ALEMBIC_REVISION": "0009_operations",
        }
        self.environment = patch.dict(os.environ, self.env, clear=True)
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_real_cookie_roundtrip_and_sanitized_result(self):
        result = smoke.run(self.env)
        self.assertTrue(result["healthy"])
        self.assertEqual(self.logout_count, 1)
        self.assertEqual(self.server.origin_seen, self.env["SMOKE_PWA_URL"])
        self.assertNotIn("synthetic-cookie", json.dumps(result))
        self.assertNotIn("synthetic-password", json.dumps(result))

    def test_migration_mismatch_fails_and_logs_out(self):
        self.payload["alembic_revisions"] = ["old", "0009_operations"]
        with self.assertRaisesRegex(smoke.SmokeFailure, "migration_mismatch"):
            smoke.run(self.env)
        self.assertEqual(self.logout_count, 1)

    def test_worker_missing_and_dead_letter_each_block(self):
        for worker, queue, expected in [
            (False, [], "worker_not_recent"),
            (True, [{"status": "dead", "count": 1}], "dead_letter_present"),
        ]:
            with self.subTest(expected=expected):
                self.payload["worker_recent"], self.payload["queue"] = worker, queue
                with self.assertRaisesRegex(smoke.SmokeFailure, expected):
                    smoke.run(self.env)

    def test_forbidden_response_is_not_an_approved_smoke(self):
        self.operation_status = 403
        with self.assertRaisesRegex(smoke.SmokeFailure, "request_failed"):
            smoke.run(self.env)

    def test_wrong_athlete_response_rejected(self):
        self.env.update(
            SMOKE_ATHLETE_EMAIL="synthetic-athlete@example.com",
            SMOKE_ATHLETE_PASSWORD="synthetic-password",
        )
        with self.assertRaisesRegex(smoke.SmokeFailure, "athlete_scope_violation"):
            smoke.run(self.env)
        self.assertEqual(self.logout_count, 2)

    def test_response_token_rejected_without_printing(self):
        self.login_token = True
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(smoke.main(), 1)
        for secret in (
            "forbidden-secret",
            "synthetic-iam",
            "synthetic-password",
            "synthetic-admin@example.com",
        ):
            self.assertNotIn(secret, output.getvalue())

    def test_non_tls_and_credential_urls_rejected(self):
        for url in (
            "http://example.com",
            "https://user:secret@example.com",
            "https://example.com?token=secret",
            "https://example.com/path",
        ):
            with self.subTest(url=url), self.assertRaises(smoke.SmokeFailure):
                smoke.origin(url)


class BackupContract(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 30, 18, tzinfo=UTC)

    def record(self, hours, status="SUCCESSFUL"):
        return {
            "endTime": (self.now - timedelta(hours=hours)).isoformat(),
            "status": status,
            "instance": "private-instance",
            "location": "private-location",
        }

    def test_recent_success_and_sanitized_inventory(self):
        result = backups.evaluate([self.record(1)], self.now)
        self.assertTrue(result["healthy"])
        self.assertNotIn("private", json.dumps(result))

    def test_stale_missing_failed_overdue_block(self):
        for inventory in (
            [],
            [self.record(37)],
            [self.record(1, "FAILED"), self.record(2)],
            [self.record(1, "OVERDUE"), self.record(2)],
            [self.record(1, "UNKNOWN"), self.record(2)],
        ):
            with self.subTest(inventory=inventory):
                self.assertFalse(backups.evaluate(inventory, self.now)["healthy"])

    def test_gcloud_failure_is_sanitized_and_blocking(self):
        output = io.StringIO()
        with (
            patch.dict(
                os.environ,
                {
                    "GCP_PROJECT_ID": "synthetic-project",
                    "CLOUD_SQL_INSTANCE": "synthetic-instance",
                },
            ),
            patch.object(
                backups.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(
                    1, "gcloud", stderr="sensitive-provider-error"
                ),
            ),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(backups.main(), 1)
        self.assertNotIn("sensitive-provider-error", output.getvalue())


class RecoveryScriptContract(unittest.TestCase):
    def scenario(self, **override):
        # Fake CLI only: executing this test cannot reach Google Cloud.
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            cli = folder / "gcloud"
            calls = folder / "calls.jsonl"
            cli.write_text("""#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ['MOCK_CALLS'], 'a') as stream:
    stream.write(json.dumps(args) + '\\n')
if args[:3] == ['sql', 'instances', 'list']:
    if os.environ.get('MOCK_LIST_FAILED') == 'true': sys.exit(1)
    if os.environ.get('MOCK_TARGET_EXISTS') == 'true': print('synthetic-target')
elif args[:3] == ['sql', 'instances', 'clone']:
    print('synthetic-operation')
elif args[:3] == ['sql', 'operations', 'wait']:
    if os.environ.get('MOCK_WAIT_FAILED') == 'true': sys.exit(1)
elif args[:3] == ['sql', 'instances', 'describe'] and args[3] == 'synthetic-target':
    print(os.environ.get('MOCK_TARGET_STATE', 'RUNNABLE'))
""")
            cli.chmod(0o700)
            env = {
                **os.environ,
                "PATH": str(folder) + os.pathsep + os.environ["PATH"],
                "MOCK_CALLS": str(calls),
                "CONFIRM_RESTORE": "RESTORE_TO_NEW_INSTANCE",
                "GCP_PROJECT_ID": "synthetic-project",
                "SOURCE_INSTANCE": "synthetic-source",
                "TARGET_INSTANCE": "synthetic-target",
                "POINT_IN_TIME": "2026-09-30T12:00:00Z",
                **override,
            }
            result = subprocess.run(
                [
                    "bash",
                    str(Path(__file__).resolve().parents[1] / "restore-cloud-sql.sh"),
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            invoked = (
                [json.loads(line) for line in calls.read_text().splitlines()]
                if calls.exists()
                else []
            )
            return result, invoked

    def test_permission_error_or_existing_target_never_clones(self):
        for override in ({"MOCK_LIST_FAILED": "true"}, {"MOCK_TARGET_EXISTS": "true"}):
            with self.subTest(override=override):
                result, invoked = self.scenario(**override)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(
                    any(
                        command[:3] == ["sql", "instances", "clone"]
                        for command in invoked
                    )
                )

    def test_invalid_confirmation_and_timestamp_never_call_cloud_cli(self):
        for override in (
            {"CONFIRM_RESTORE": "YES"},
            {"POINT_IN_TIME": "2026-02-31T12:00:00Z"},
        ):
            with self.subTest(override=override):
                result, invoked = self.scenario(**override)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(invoked, [])

    def test_waits_and_marks_functional_restore_unverified(self):
        result, invoked = self.scenario()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(
            any(command[:3] == ["sql", "operations", "wait"] for command in invoked)
        )
        report = json.loads(result.stdout.splitlines()[0])
        self.assertTrue(report["clone_ready"])
        self.assertFalse(report["application_restored"])
        self.assertFalse(report["rto_measured"])
        self.assertGreaterEqual(report["provision_seconds"], 0)

    def test_failed_wait_or_non_runnable_cannot_claim_success(self):
        for override in ({"MOCK_WAIT_FAILED": "true"}, {"MOCK_TARGET_STATE": "FAILED"}):
            with self.subTest(override=override):
                result, _ = self.scenario(**override)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("pitr_clone_verified", result.stdout)


if __name__ == "__main__":
    unittest.main()
