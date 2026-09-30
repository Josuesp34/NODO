#!/usr/bin/env python3
"""Guarded synthetic fixtures and authenticated HTTP benchmarks; no cloud resources."""

import argparse
import asyncio
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from datetime import time as day_time
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "ops/fixtures/qa-corpus-v1.json"
COACH = "qa-coach@example.com"
REVOKED = "qa-revoked@example.com"
PASSWORD = "Nodo-Synthetic-Only-2026!"  # Public, deliberately synthetic local account password.


def guard():
    if (
        os.environ.get("ENVIRONMENT") != "development"
        or os.environ.get("NODO_SYNTHETIC_QA") != "1"
    ):
        raise SystemExit("Requiere ENVIRONMENT=development y NODO_SYNTHETIC_QA=1")


def read_config(path):
    content = Path(path).read_bytes()
    config = json.loads(content)
    if (
        config["athletes"] != 70
        or config["weeks"] != 12
        or date.fromisoformat(config["start_date"]).weekday() != 0
    ):
        raise SystemExit(
            "El corpus requiere 70 atletas, 12 semanas y comienzo en lunes"
        )
    return config, hashlib.sha256(content).hexdigest()


def at_zone(day, zone, hour=7, minute=0):
    return datetime.combine(day, day_time(hour, minute), ZoneInfo(zone)).astimezone(UTC)


def prescription(sport):
    if sport == "running":
        step = {
            "kind": "work",
            "distance_m": 1000,
            "target": {
                "metric": "pace",
                "unit": "sec_per_km",
                "minimum": 260,
                "maximum": 320,
            },
        }
        return [{"repetitions": 3, "steps": [step]}], 840, 3000, 280
    if sport == "swimming":
        step = {
            "kind": "work",
            "distance_m": 100,
            "target": {
                "metric": "pace",
                "unit": "sec_per_100m",
                "minimum": 90,
                "maximum": 120,
            },
        }
        return [{"repetitions": 4, "steps": [step]}], 440, 400, 110
    if sport == "cycling":
        step = {
            "kind": "work",
            "duration_sec": 600,
            "target": {
                "metric": "power",
                "unit": "watts",
                "minimum": 180,
                "maximum": 240,
            },
        }
        return [{"repetitions": 3, "steps": [step]}], 1800, 15000, 600
    return (
        [
            {
                "repetitions": 1,
                "steps": [
                    {"kind": "work", "distance_m": 400},
                    {"kind": "work", "duration_sec": 1200},
                    {"kind": "work", "distance_m": 2000},
                ],
            }
        ],
        2400,
        10000,
        800,
    )


async def seed(config, config_hash):
    sys.path.insert(0, str(ROOT / "backend/api"))
    from app.core.config import settings
    from app.core.security import hash_password
    from app.domain.metrics import (
        calculate_banister_trimp,
        calculate_training_status,
        calculate_tss,
    )
    from app.infrastructure.database.models import (
        Activity,
        PrescribedWorkout,
        TelemetryRecord,
        User,
    )
    from app.infrastructure.database.models.product import (
        ActivityLap,
        AthleteGroup,
        AthleteProfile,
        AuditLog,
        Checkin,
        CoachAthleteAssignment,
        CommercialPlan,
        Competition,
        Complaint,
        ComplaintUpdate,
        Consent,
        DailyLoad,
        GroupMembership,
        Observation,
        Organization,
        OrganizationMembership,
        ReviewItem,
        Subscription,
        UserRoleAssignment,
    )
    from app.infrastructure.database.models.user import UserRole
    from sqlalchemy import func, select
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    host = urlsplit(
        settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
    ).hostname
    if host not in {"127.0.0.1", "localhost", "postgres", "host.docker.internal"}:
        raise SystemExit(
            "La siembra sólo admite PostgreSQL local/Docker; no escribe bases remotas"
        )
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    started = time.perf_counter()
    start = date.fromisoformat(config["start_date"])
    days = [start + timedelta(days=i) for i in range(config["weeks"] * 7)]
    counts = Counter()
    async with sessions() as db:
        marker = await db.scalar(
            select(AuditLog).where(
                AuditLog.entity == "qa_corpus", AuditLog.entity_id == config_hash
            )
        )
        if marker is not None:
            await engine.dispose()
            return {
                "status": "already_seeded",
                "config_sha256": config_hash,
                **marker.after,
            }
        names = [
            COACH,
            REVOKED,
            *[f"qa-athlete-{i + 1:02d}@example.com" for i in range(config["athletes"])],
        ]
        if await db.scalar(
            select(func.count()).select_from(User).where(User.email.in_(names))
        ):
            raise SystemExit(
                "Hay cuentas QA existentes sin marcador compatible; no se sobrescriben"
            )
        password_hash = hash_password(os.environ.get("NODO_QA_PASSWORD", PASSWORD))
        users = [
            User(
                email=email,
                hashed_password=password_hash,
                first_name="QA",
                last_name=f"Sintético {index:02d}",
                role=UserRole.COACH if index < 2 else UserRole.ATHLETE,
                timezone=config["timezones"][(index - 2) % len(config["timezones"])],
                email_verified_at=datetime.now(UTC),
            )
            for index, email in enumerate(names)
        ]
        db.add_all(users)
        organization = Organization(
            name="QA sintética — sin atletas reales",
            slug=config["version"],
            status="active",
        )
        plan = CommercialPlan(
            name=f"QA {config['version']}", athlete_limit=1000, active=True
        )
        db.add_all([organization, plan])
        await db.flush()
        coach, revoked, *athletes = users
        db.add(
            Subscription(
                organization_id=organization.id,
                plan_id=plan.id,
                starts_on=start,
                ends_on=date(2030, 1, 1),
                status="active",
            )
        )
        group = AthleteGroup(
            organization_id=organization.id,
            coach_id=coach.id,
            name="QA cuatro disciplinas",
        )
        db.add(group)
        await db.flush()
        for index, user in enumerate(users):
            role = "coach" if index < 2 else "athlete"
            db.add(UserRoleAssignment(user_id=user.id, role=role))
            db.add(
                OrganizationMembership(
                    organization_id=organization.id,
                    user_id=user.id,
                    role="owner" if index == 0 else role,
                    status="active",
                )
            )
            for scope in [
                "training_data_processing",
                "assistant_data_processing",
                "health_context_processing",
            ]:
                db.add(
                    Consent(
                        user_id=user.id,
                        scope=scope,
                        version="pilot-v1",
                        granted_at=datetime.now(UTC),
                    )
                )
        for index, athlete in enumerate(athletes):
            sport = config["sports"][index % len(config["sports"])]
            athlete.coach_id = coach.id
            for owner, state in [(coach, "active"), (revoked, "revoked")]:
                db.add(
                    CoachAthleteAssignment(
                        organization_id=organization.id,
                        coach_id=owner.id,
                        athlete_id=athlete.id,
                        status=state,
                        revoked_at=datetime.now(UTC) if state == "revoked" else None,
                    )
                )
            if index % config["multi_role_every"] == 0:
                db.add(UserRoleAssignment(user_id=athlete.id, role="coach"))
                counts["multi_role_profiles"] += 1
            profile = AthleteProfile(
                athlete_id=athlete.id,
                sports=[sport],
                timezone=athlete.timezone,
                goals={
                    "objective": "Objetivo sintético QA; no usar con atletas reales"
                },
                availability={"available_weekdays": config["available_weekdays"]},
                rest_hr=50,
                max_hr=190,
                ftp=250 if sport in {"cycling", "triathlon"} else None,
                threshold_pace_sec_per_km=280
                if sport in {"running", "triathlon"}
                else None,
                trimp_variant="banister_male",
                source=config["version"],
                valid_from=start,
            )
            db.add(profile)
            db.add(
                GroupMembership(
                    group_id=group.id,
                    athlete_id=athlete.id,
                    overrides={"available_weekdays": config["available_weekdays"]},
                )
            )
            db.add(
                Competition(
                    athlete_id=athlete.id,
                    coach_id=coach.id,
                    name="Objetivo sintético QA",
                    competition_date=days[-1],
                    discipline=sport,
                    priority="A",
                )
            )
            steps, duration, distance, lap_duration = prescription(sport)
            workouts = {}
            for ordinal, day in enumerate(days):
                db.add(
                    Checkin(
                        athlete_id=athlete.id,
                        local_date=day,
                        fatigue=(ordinal + index) % 11,
                        perceived_rest=(ordinal + index + 3) % 11,
                        stress=(ordinal + index + 5) % 11,
                        notes="QA sintético: descanso"
                        if day.weekday() not in config["available_weekdays"]
                        else "QA sintético: sesión programada",
                    )
                )
                counts["checkin_days"] += 1
                if day.weekday() not in config["available_weekdays"]:
                    counts["rest_days"] += 1
                    continue
                workout = PrescribedWorkout(
                    athlete_id=athlete.id,
                    coach_id=coach.id,
                    title=f"QA {sport} · semana {ordinal // 7 + 1} · día {ordinal + 1}",
                    description="Fixture reproducible, sin indicación deportiva real",
                    sport_type=sport,
                    scheduled_date=at_zone(day, athlete.timezone, 23, 30)
                    if ordinal % 23 == 0
                    else at_zone(day, athlete.timezone),
                    steps=steps,
                    status="draft" if ordinal % 11 == 0 else "published",
                    version=1,
                )
                workouts[ordinal] = workout
                db.add(workout)
                counts["workouts"] += 1
            await db.flush()
            activities = []
            daily = defaultdict(float)
            for ordinal, workout in workouts.items():
                if ordinal % config["missing_every"] == 0:
                    counts["missing_sessions"] += 1
                    continue
                day = days[ordinal]
                recorded_day = day + timedelta(days=1) if ordinal % 23 == 0 else day
                started_at = (
                    at_zone(recorded_day, athlete.timezone, 0, 5)
                    if ordinal % 23 == 0
                    else at_zone(day, athlete.timezone)
                )
                partial = ordinal % config["partial_every"] == 0
                late = ordinal % config["late_every"] == 0
                trimp = (
                    None
                    if partial
                    else calculate_banister_trimp(duration / 60, 150, 50, 190, True)
                )
                activity = Activity(
                    athlete_id=athlete.id,
                    file_name="qa-generated-summary",
                    file_hash=hashlib.sha256(
                        f"{config_hash}:{index}:{ordinal}".encode()
                    ).hexdigest(),
                    provider="qa_synthetic",
                    external_id=f"{config['version']}:{index}:{ordinal}",
                    sport_type=sport,
                    timezone=athlete.timezone,
                    start_time=started_at,
                    total_duration_sec=duration,
                    total_distance_m=None if partial else distance,
                    avg_heart_rate=None if partial else 150,
                    max_heart_rate=None if partial else 175,
                    avg_speed_mps=None if partial else distance / duration,
                    calculated_trimp=trimp,
                    calculated_tss=calculate_tss(duration, 220, 250)
                    if sport == "cycling"
                    else None,
                    prescribed_workout_id=workout.id
                    if workout.status == "published"
                    else None,
                    created_at=started_at + timedelta(days=3 if late else 0),
                )
                db.add(activity)
                activities.append(activity)
                if trimp is not None:
                    daily[recorded_day] += trimp
                counts["activities"] += 1
                counts["partial_activities"] += int(partial)
                counts["late_activities"] += int(late)
                counts["cross_midnight_activities"] += int(ordinal % 23 == 0)
            if index % config["ambiguous_every"] == 0 and activities:
                original = activities[0]
                second = Activity(
                    athlete_id=athlete.id,
                    file_name="qa-second-linked-session",
                    file_hash=hashlib.sha256(
                        f"{config_hash}:{index}:second".encode()
                    ).hexdigest(),
                    provider="qa_synthetic",
                    external_id=f"{config['version']}:{index}:second",
                    sport_type=sport,
                    timezone=athlete.timezone,
                    start_time=original.start_time + timedelta(hours=1),
                    total_duration_sec=duration,
                    total_distance_m=distance,
                    avg_heart_rate=150,
                    calculated_trimp=original.calculated_trimp,
                    prescribed_workout_id=original.prescribed_workout_id,
                )
                db.add(second)
                activities.append(second)
                counts["ambiguous_linked_sessions"] += 1
                counts["activities"] += 1
                daily[
                    second.start_time.astimezone(ZoneInfo(athlete.timezone)).date()
                ] += second.calculated_trimp or 0
            await db.flush()
            for activity in activities:
                repetitions = (
                    len(steps[0]["steps"])
                    if sport == "triathlon"
                    else steps[0]["repetitions"]
                )
                for lap_index in range(repetitions):
                    db.add(
                        ActivityLap(
                            activity_id=activity.id,
                            lap_index=lap_index,
                            started_at=activity.start_time
                            + timedelta(seconds=lap_index * lap_duration),
                            duration_sec=lap_duration,
                            distance_m=None
                            if activity.total_distance_m is None
                            else activity.total_distance_m / repetitions,
                            avg_heart_rate=activity.avg_heart_rate,
                            avg_power=220 if sport == "cycling" else None,
                        )
                    )
                    counts["laps"] += 1
                for point in range(3):
                    db.add(
                        TelemetryRecord(
                            activity_id=activity.id,
                            timestamp=activity.start_time
                            + timedelta(seconds=point * lap_duration),
                            heart_rate=activity.avg_heart_rate,
                        )
                    )
                    counts["telemetry_points"] += 1
            ctl = atl = 0.0
            for ordinal, day in enumerate(days):
                load = daily[day]
                result = calculate_training_status(load, ctl, atl)
                ctl, atl = result["ctl"], result["atl"]
                db.add(
                    DailyLoad(
                        athlete_id=athlete.id,
                        local_date=day,
                        load_unit="trimp",
                        load_value=load,
                        **result,
                        formula_version="ewma-42-7-v1",
                        recomputed_at=datetime.now(UTC),
                    )
                )
                counts["daily_load_days"] += 1
                if ordinal % 7 == 0:
                    db.add(
                        Observation(
                            athlete_id=athlete.id,
                            metric_type="hrv_rmssd",
                            value=40 + index % 30,
                            unit="ms",
                            method="qa_fixture_rmssd",
                            source=config["version"],
                            observed_start=at_zone(day, athlete.timezone),
                            observed_end=at_zone(day, athlete.timezone),
                            received_at=at_zone(
                                day + timedelta(days=2), athlete.timezone
                            ),
                            timezone=athlete.timezone,
                            quality="estimated",
                            external_id=f"qa:{index}:{ordinal}",
                        )
                    )
            complaint = Complaint(
                athlete_id=athlete.id,
                zone="Rodilla QA",
                laterality="left",
                intensity_0_10=8,
                started_on=start + timedelta(days=20),
                limits_movement=True,
                note="Caso sintético de empeoramiento",
                status="reported",
                version=3,
            )
            db.add(complaint)
            await db.flush()
            db.add(
                ComplaintUpdate(
                    complaint_id=complaint.id,
                    actor_id=athlete.id,
                    intensity_0_10=8,
                    limits_movement=True,
                    note="Reapertura sintética después de cierre",
                )
            )
            review = ReviewItem(
                athlete_id=athlete.id,
                complaint_id=complaint.id,
                kind="complaint",
                priority="high",
                reason="QA: molestia sintética reabierta; no ocultar por otros indicadores",
                dedupe_key=f"complaint:{complaint.id}",
                status="follow_up" if index % 2 else "open",
                version=3,
            )
            db.add(review)
            await db.flush()
            db.add(
                AuditLog(
                    actor_id=coach.id,
                    entity="review_item",
                    entity_id=str(review.id),
                    action="closed",
                    after={"note": "Cierre previo sintético"},
                    at=at_zone(start + timedelta(days=19), athlete.timezone),
                )
            )
            if activities:
                original = activities[0]
                try:
                    async with db.begin_nested():
                        db.add(
                            Activity(
                                athlete_id=athlete.id,
                                file_name="qa-duplicate",
                                file_hash=original.file_hash,
                                provider=original.provider,
                                external_id=original.external_id,
                                start_time=original.start_time,
                                sport_type=sport,
                                timezone=athlete.timezone,
                            )
                        )
                        await db.flush()
                except IntegrityError:
                    counts["duplicates_rejected"] += 1
                else:
                    raise RuntimeError("El esquema no bloqueó una actividad duplicada")
            counts["profiles"] += 1
            await db.flush()
        report = {
            "version": config["version"],
            "athletes": len(athletes),
            "days_per_athlete": len(days),
            "start": str(days[0]),
            "end": str(days[-1]),
            "counts": dict(counts),
            "duration_seconds": round(time.perf_counter() - started, 3),
        }
        db.add(
            AuditLog(
                actor_id=coach.id,
                entity="qa_corpus",
                entity_id=config_hash,
                action="seed_synthetic",
                after=report,
                at=datetime.now(UTC),
            )
        )
        await db.commit()
    await engine.dispose()
    return {"status": "seeded", "config_sha256": config_hash, **report}


def percentile(values, pct):
    return sorted(values)[max(0, math.ceil(len(values) * pct) - 1)]


def benchmark(config, config_hash, base_url, concurrency, rounds):
    import httpx

    url = urlsplit(base_url)
    if (
        url.hostname not in {"127.0.0.1", "localhost", "api", "host.docker.internal"}
        or url.scheme != "http"
    ):
        raise SystemExit(
            "El benchmark sólo consulta la API local HTTP, no producción ni cloud"
        )
    base_url = base_url.rstrip("/")
    password = os.environ.get("NODO_QA_PASSWORD", PASSWORD)
    with httpx.Client(
        timeout=30, limits=httpx.Limits(max_connections=max(10, concurrency * 2))
    ) as client:

        def login(email):
            response = client.post(
                base_url + "/auth/login", json={"email": email, "password": password}
            )
            response.raise_for_status()
            return {"Authorization": f"Bearer {response.json()['access_token']}"}

        headers = login(COACH)
        response = client.get(base_url + "/auth/athletes", headers=headers)
        response.raise_for_status()
        athletes = [
            a
            for a in response.json()
            if a["email"].startswith("qa-athlete-")
            and a["email"].endswith("@example.com")
        ]
        if len(athletes) != config["athletes"]:
            raise SystemExit(f"Corpus incompleto: {len(athletes)}/70 atletas")
        start = date.fromisoformat(config["start_date"])
        end = start + timedelta(days=config["weeks"] * 7 - 1)
        tasks = [
            (kind, a["id"])
            for _ in range(rounds)
            for a in athletes
            for kind in ["calendar", "activities"]
        ]

        def query(task):
            kind, aid = task
            path = (
                f"/athletes/{aid}/workouts?start={start}&end={end}"
                if kind == "calendar"
                else f"/athletes/{aid}/activities/page?limit=20&offset=0"
            )
            began = time.perf_counter()
            result = client.get(base_url + path, headers=headers)
            result.raise_for_status()
            body = result.json()
            if (
                kind == "activities"
                and body["total"] > 20
                and body["next_offset"] != 20
            ):
                raise RuntimeError("Paginación inconsistente")
            return kind, time.perf_counter() - began, len(result.content)

        # Warm the actual HTTP/API/DB path before measuring.
        query(tasks[0])
        began = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            samples = list(executor.map(query, tasks))
        elapsed = time.perf_counter() - began
        stats = {}
        for kind in ["calendar", "activities"]:
            values = [sample[1] for sample in samples if sample[0] == kind]
            p95 = percentile(values, 0.95)
            limit = config["limits_seconds"][f"{kind}_p95"]
            stats[kind] = {
                "requests": len(values),
                "p50_seconds": round(statistics.median(values), 4),
                "p95_seconds": round(p95, 4),
                "max_seconds": round(max(values), 4),
                "limit_seconds": limit,
                "passed": p95 < limit,
            }
        revoked = login(REVOKED)
        denied = client.get(
            base_url + f"/athletes/{athletes[0]['id']}/activities/page", headers=revoked
        ).status_code
        if denied != 404:
            raise RuntimeError(f"La asignación revocada permitió acceso: {denied}")
        statuses = {}
        for index, sport in enumerate(config["sports"]):
            representative = next(
                a
                for a in athletes
                if a["email"] == f"qa-athlete-{index + 1:02d}@example.com"
            )
            compared = client.get(
                base_url
                + f"/athletes/{representative['id']}/activities/comparison?start={start}&end={end}",
                headers=headers,
            )
            compared.raise_for_status()
            statuses[sport] = dict(
                Counter(row["status"] for row in compared.json()["workouts"])
            )
            if sport == "swimming":
                for row in compared.json()["workouts"]:
                    for lap in row["laps"]:
                        if (
                            lap.get("target")
                            and lap["target"]["unit"] != "sec_per_100m"
                        ):
                            raise RuntimeError("La natación mezcló unidades de carrera")
        review = client.get(base_url + "/review-items", headers=headers)
        review.raise_for_status()
        if len(review.json()) != 70 or any(
            item["priority"] != "high" for item in review.json()
        ):
            raise RuntimeError("La bandeja no conserva visibles las molestias QA")
        multirole = []
        for index, athlete in enumerate(athletes):
            if athlete["email"] not in {
                f"qa-athlete-{i + 1:02d}@example.com"
                for i in range(0, 70, config["multi_role_every"])
            }:
                continue
            own = login(athlete["email"])
            own_response = client.get(
                base_url
                + f"/athletes/{athlete['id']}/workouts?start={start}&end={end}",
                headers=own,
            )
            own_response.raise_for_status()
            if any(w["status"] != "published" for w in own_response.json()):
                raise RuntimeError(
                    "Atleta multirol sin asignación coach accedió a borradores de otro entrenador"
                )
            multirole.append(athlete["id"])
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    return {
        "version": config["version"],
        "config_sha256": config_hash,
        "git_sha": sha,
        "working_tree_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            )
        ),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "measured_at": datetime.now(UTC).isoformat(),
        "hardware": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
        },
        "transport": "authenticated HTTP → API → PostgreSQL",
        "concurrency": concurrency,
        "rounds": rounds,
        "athletes": len(athletes),
        "requests": len(tasks),
        "elapsed_seconds": round(elapsed, 3),
        "throughput_requests_per_second": round(len(tasks) / elapsed, 2),
        "results": stats,
        "checks": {
            "revoked_status": denied,
            "multi_role_profiles": len(multirole),
            "complaints_visible": len(review.json()),
            "comparison_statuses": statuses,
        },
        "passed": all(row["passed"] for row in stats.values()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["seed", "benchmark"])
    parser.add_argument("--config", default=str(CONFIG))
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--output")
    args = parser.parse_args()
    guard()
    config, config_hash = read_config(args.config)
    if not 1 <= args.concurrency <= 32 or not 1 <= args.rounds <= 20:
        raise SystemExit("Concurrencia 1–32; rondas 1–20")
    result = (
        asyncio.run(seed(config, config_hash))
        if args.action == "seed"
        else benchmark(config, config_hash, args.url, args.concurrency, args.rounds)
    )
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload)
    print(payload)
    if result.get("passed") is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
