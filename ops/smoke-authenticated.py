#!/usr/bin/env python3
"""Read-only product smoke after cookie login, with sanitized output and no redirects."""

import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

MAX_RESPONSE = 2 * 1024 * 1024


class SmokeFailure(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


def origin(value):
    parsed = urllib.parse.urlsplit(value)
    local = (
        os.environ.get("SMOKE_ALLOW_LOOPBACK") == "true"
        and parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost"}
    )
    if (
        (parsed.scheme != "https" and not local)
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise SmokeFailure("invalid_origin")
    return value.rstrip("/")


class Client:
    def __init__(self, base):
        self.base = origin(base)
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPCookieProcessor(self.cookies)
        )

    def request(self, path, *, body=None, headers=None, expect=200):
        request_headers = {"Accept": "application/json", **(headers or {})}
        method = "GET"
        data = None
        if body is not None:
            method = "POST"
            data = json.dumps(body).encode()
            request_headers.update(
                {"Content-Type": "application/json", "Origin": self.base}
            )
        request = urllib.request.Request(
            self.base + path, data=data, headers=request_headers, method=method
        )
        try:
            with self.opener.open(request, timeout=20) as response:
                if response.status != expect:
                    raise SmokeFailure("unexpected_status")
                payload = response.read(MAX_RESPONSE + 1)
                if len(payload) > MAX_RESPONSE:
                    raise SmokeFailure("response_limit")
                if not payload:
                    return None
                return json.loads(payload)
        except (urllib.error.URLError, ValueError):
            # Exceptions may include URLs, response bodies, or provider details.
            raise SmokeFailure("request_failed") from None

    def login(self, email, password):
        response = self.request(
            "/api/session/login", body={"email": email, "password": password}
        )
        if not isinstance(response, dict) or any(
            key.endswith("token") for key in response
        ):
            raise SmokeFailure("login_contract")
        session_cookies = [
            cookie
            for cookie in self.cookies
            if cookie.name.endswith(("_access", "_refresh"))
        ]
        if not session_cookies:
            raise SmokeFailure("session_cookie_missing")
        for cookie in session_cookies:
            attributes = {key.lower(): value for key, value in cookie._rest.items()}
            if (
                "httponly" not in attributes
                or str(attributes.get("samesite", "")).lower() != "lax"
                or (self.base.startswith("https://") and not cookie.secure)
            ):
                raise SmokeFailure("session_cookie_unprotected")
        identity = self.request("/api/session/me")
        if not isinstance(identity, dict) or not isinstance(identity.get("id"), int):
            raise SmokeFailure("identity_contract")
        return identity

    def logout(self):
        self.request("/api/session/logout", body={}, expect=204)


def require(condition, check):
    if not condition:
        raise SmokeFailure(check)


def run(env=os.environ):
    expected_revision = env.get("SMOKE_EXPECTED_ALEMBIC_REVISION", "")
    require(bool(expected_revision), "expected_revision_required")
    require(
        bool(env.get("SMOKE_ADMIN_EMAIL") and env.get("SMOKE_ADMIN_PASSWORD")),
        "admin_credentials_required",
    )
    pwa = Client(env.get("SMOKE_PWA_URL", ""))
    api = Client(env.get("SMOKE_API_URL", ""))
    require(bool(env.get("SMOKE_API_ID_TOKEN")), "api_identity_required")
    health = api.request(
        "/health",
        headers={"X-Serverless-Authorization": "Bearer " + env["SMOKE_API_ID_TOKEN"]},
    )
    require(
        isinstance(health, dict) and health.get("status") == "ok", "health_contract"
    )
    sessions = []
    try:
        sessions.append(pwa)
        pwa.login(env["SMOKE_ADMIN_EMAIL"], env["SMOKE_ADMIN_PASSWORD"])
        operations = pwa.request("/api/nodo/admin/operations")
        require(isinstance(operations, dict), "operations_contract")
        require(
            operations.get("alembic_revisions") == [expected_revision],
            "migration_mismatch",
        )
        require(operations.get("worker_recent") is True, "worker_not_recent")
        require(operations.get("stale_running_count") == 0, "worker_stale_lease")
        queue = operations.get("queue")
        require(isinstance(queue, list), "queue_contract")
        require(
            all(
                isinstance(item, dict) and isinstance(item.get("count"), int)
                for item in queue
            ),
            "queue_contract",
        )
        require(
            not any(
                item.get("status") == "dead" and item["count"] > 0 for item in queue
            ),
            "dead_letter_present",
        )
        athletes = pwa.request("/api/nodo/auth/athletes")
        require(isinstance(athletes, list), "athlete_list_contract")
        for role in ("COACH", "ATHLETE"):
            email, password = (
                env.get(f"SMOKE_{role}_EMAIL"),
                env.get(f"SMOKE_{role}_PASSWORD"),
            )
            require(
                bool(email) == bool(password), f"{role.lower()}_credentials_incomplete"
            )
            if not email:
                continue
            client = Client(env["SMOKE_PWA_URL"])
            sessions.append(client)
            identity = client.login(email, password)
            if role == "COACH":
                require(
                    isinstance(client.request("/api/nodo/auth/athletes"), list),
                    "coach_list_contract",
                )
            else:
                today = datetime.now(UTC).date()
                path = f"/api/nodo/athletes/{identity['id']}/workouts?start={today}&end={today + timedelta(days=7)}"
                workouts = client.request(path)
                require(isinstance(workouts, list), "workout_list_contract")
                require(
                    all(
                        item.get("athlete_id") == identity["id"]
                        and item.get("status") == "published"
                        for item in workouts
                    ),
                    "athlete_scope_violation",
                )
        return {
            "event": "release_smoke",
            "healthy": True,
            "migration_verified": True,
            "worker_verified": True,
            "sessions_checked": len(sessions),
        }
    finally:
        logout_failed = False
        for client in sessions:
            try:
                client.logout()
            except SmokeFailure:
                # Local cookie state is still destroyed; report the failed cleanup.
                client.cookies.clear()
                logout_failed = True
        if logout_failed:
            raise SmokeFailure("smoke_logout_failed") from None


def main():
    try:
        result = run()
    except SmokeFailure as exc:
        print(
            json.dumps({"event": "release_smoke", "healthy": False, "check": str(exc)})
        )
        return 1
    except Exception:  # noqa: BLE001 -- CLI boundary must redact cookies, URLs, bodies and credentials.
        print(
            json.dumps(
                {
                    "event": "release_smoke",
                    "healthy": False,
                    "check": "unexpected_failure",
                }
            )
        )
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
