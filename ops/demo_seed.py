"""Semilla por API para la base sintética dedicada de compose.demo.yml."""

import argparse
from datetime import UTC, datetime, timedelta
import json
import os
import urllib.error
import urllib.request

from garmin_fit_sdk import Encoder, Profile


def synthetic_fit(start):
    encoder = Encoder()
    encoder.on_mesg(Profile["mesg_num"]["FILE_ID"], {"manufacturer": "development", "product": 1, "type": "activity", "time_created": start})
    for second in (0, 300, 600):
        encoder.on_mesg(Profile["mesg_num"]["RECORD"], {"timestamp": start + timedelta(seconds=second), "heart_rate": 150, "distance": second * 2.5})
    encoder.on_mesg(Profile["mesg_num"]["SESSION"], {"timestamp": start + timedelta(seconds=600), "start_time": start, "total_timer_time": 600, "total_elapsed_time": 600, "total_distance": 1500, "avg_heart_rate": 150, "sport": "running"})
    encoder.on_mesg(Profile["mesg_num"]["LAP"], {"timestamp": start + timedelta(seconds=600), "start_time": start, "total_timer_time": 600, "total_distance": 1500, "avg_heart_rate": 150})
    return bytes(encoder.close())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://api:8000")
    args = parser.parse_args()
    if os.environ.get("ENVIRONMENT") != "development":
        raise RuntimeError("La semilla sólo se permite en la demo development")
    password = os.environ["NODO_DEMO_PASSWORD"]
    base = args.api.rstrip("/") + "/api/v1"

    def call(method, path, body=None, token=None, expected=(200, 201, 204), raw=None, content_type=None):
        headers = {"Content-Type": content_type or "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(base + path, data=raw if raw is not None else (json.dumps(body).encode() if body is not None else None), headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                if response.status not in expected:
                    raise RuntimeError(f"Semilla: {method} {path} devolvió {response.status}")
                data = response.read()
                return json.loads(data) if data else None
        except urllib.error.HTTPError as error:
            if error.code in expected:
                return None
            raise RuntimeError(f"Semilla: {method} {path} devolvió {error.code}") from None

    def coach(email, name):
        call("POST", "/auth/coaches", {"email": email, "first_name": name, "last_name": "Demo", "timezone": "America/Mexico_City", "password": password}, expected=(201, 409))
        token = call("POST", "/auth/login", {"email": email, "password": password})["access_token"]
        return token, call("GET", "/auth/me", token=token)

    # Usar el bootstrap autorizado y la API administrativa; no elevar cuentas mediante SQL.
    import asyncio
    from app.api.schemas import CoachRegistration
    from app.bootstrap_admin import create_first_admin
    from app.core.database import async_session_maker

    async def first_admin():
        async with async_session_maker() as db:
            return await create_first_admin(db, CoachRegistration(
                email="admin-demo@example.com", first_name="Admin", last_name="Demo", password=password, timezone="America/Mexico_City",
            ))
    asyncio.run(first_admin())
    admin_token = call("POST", "/auth/login", {"email": "admin-demo@example.com", "password": password})["access_token"]
    coach_token, coach_user = coach("coach-demo@example.com", "Coach")
    _, dual_user = coach("dual-demo@example.com", "Multirol")
    call("POST", f"/auth/users/{dual_user['id']}/roles/athlete", token=admin_token)
    today = datetime.now(UTC).replace(hour=15, minute=0, second=0, microsecond=0)
    report = {"mode": "synthetic-local", "coach_id": coach_user["id"], "dual_id": dual_user["id"], "athletes": []}
    existing = {item["email"]: item for item in call("GET", "/auth/athletes", token=coach_token)}
    for email, name in [("athlete-demo@example.com", "Atleta"), ("solo-demo@example.com", "Sin coach")]:
        if email in existing:
            athlete = existing[email]
        else:
            # Una persona sin coach ya sembrada permanece independiente al repetir la demo.
            try:
                athlete_token = call("POST", "/auth/login", {"email": email, "password": password})["access_token"]
                athlete = call("GET", "/auth/me", token=athlete_token)
            except RuntimeError:
                invitation = call("POST", "/auth/athletes", {"email": email, "first_name": name, "last_name": "Demo", "timezone": "America/Mexico_City"}, token=coach_token)
                athlete = invitation["athlete"]
                call("POST", "/auth/athletes/activate", {"invitation_token": invitation["invitation_token"], "password": password})
        athlete_token = call("POST", "/auth/login", {"email": email, "password": password})["access_token"]
        athlete_id = athlete["id"]
        if email == "solo-demo@example.com":
            call("DELETE", f"/auth/athletes/{athlete_id}", token=coach_token, expected=(204, 404))
            report["athletes"].append({"id": athlete_id, "email": email, "without_coach": True})
            continue
        root = f"/athletes/{athlete_id}"
        profile = call("GET", root + "/profile", token=coach_token, expected=(200, 404))
        if profile is None:
            call("PUT", root + "/profile", {"sports": ["running", "cycling", "swimming", "triathlon"], "timezone": "America/Mexico_City", "goals": {"purpose": "demo sintética"}, "availability": {"monday": 60}, "rest_hr": 55, "max_hr": 190, "trimp_variant": "banister_male", "source": "synthetic", "valid_from": (today - timedelta(days=90)).date().isoformat()}, token=coach_token)
        workouts = call("GET", root + f"/workouts?start={today.date()}&end={(today + timedelta(days=7)).date()}", token=coach_token)
        demo_workout = next((item for item in workouts if item["title"] == "Rodaje de demostración"), None)
        if demo_workout is None:
            demo_workout = call("POST", root + "/workouts", {"title": "Rodaje de demostración", "description": "Datos ficticios para reproducir el recorrido de NODO.", "scheduled_date": today.isoformat(), "sport_type": "running", "steps": [{"repetitions": 1, "steps": [{"kind": "work", "duration_sec": 600}]}]}, token=coach_token)
        published = call("POST", root + f"/workouts/{demo_workout['id']}/publish", {"expected_version": demo_workout["version"]}, token=coach_token)
        fit = synthetic_fit(today)
        boundary = "nodo-synthetic-fit-boundary"
        multipart = f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic.fit"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + fit + f"\r\n--{boundary}--\r\n".encode()
        uploaded = call("POST", root + "/activities/fit", token=athlete_token, raw=multipart, content_type="multipart/form-data; boundary=" + boundary)
        duplicate = call("POST", root + "/activities/fit", token=athlete_token, raw=multipart, content_type="multipart/form-data; boundary=" + boundary)
        if uploaded["activity_id"] != duplicate["activity_id"]:
            raise RuntimeError("La ingesta duplicó una actividad sintética")
        report["athletes"].append({"id": athlete_id, "email": email, "workout_id": published["id"], "activity_id": uploaded["activity_id"], "deduplication": True})
    # No imprimir tokens, códigos de activación ni contraseñas.
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
