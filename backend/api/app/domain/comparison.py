"""Deterministic comparisons; unknown observations never count as non-compliance."""

import math
from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def local_day(at: datetime, timezone: str) -> str:
    return (at.replace(tzinfo=UTC) if at.tzinfo is None else at).astimezone(ZoneInfo(timezone)).date().isoformat()


def positive(value):
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) and number > 0 else None


def difference(planned, actual, unit):
    planned = positive(planned)
    actual = float(actual) if actual is not None and math.isfinite(float(actual)) and float(actual) >= 0 else None
    return {
        "unit": unit,
        "planned": planned,
        "actual": actual,
        "delta": round(actual - planned, 3) if planned is not None and actual is not None else None,
    }


def compare_workout(workout, activity, laps):
    """Laps are aligned only when counts match, never guessed from an average."""
    if activity.sport_type != workout.sport_type or workout.sport_type == "triathlon":
        return {
            "status": "incompatible_discipline",
            "summary": [],
            "laps": [],
            "reason": "Las disciplinas o segmentos no permiten una comparación directa.",
        }
    steps = [step for group in workout.steps for _ in range(group["repetitions"]) for step in group["steps"]]
    summary = []
    for field, observed, unit in [
        ("duration_sec", activity.total_duration_sec, "seconds"),
        ("distance_m", activity.total_distance_m, "meters"),
    ]:
        # A distance prescription does not imply a planned duration, or vice versa.
        if steps and all(positive(step.get(field)) is not None for step in steps):
            summary.append(difference(sum(step[field] for step in steps), observed, unit))
    aligned = bool(steps) and len(steps) == len(laps)
    compared_laps = []
    if aligned:
        for index, (step, lap) in enumerate(zip(steps, laps, strict=True)):
            field = "duration_sec" if step.get("duration_sec") is not None else "distance_m"
            values = {
                "index": index,
                "kind": step["kind"],
                "measure": difference(
                    step.get(field), getattr(lap, field), "seconds" if field == "duration_sec" else "meters"
                ),
            }
            target = step.get("target")
            if target:
                actual = None
                if target["metric"] == "heart_rate":
                    actual = positive(lap.avg_heart_rate)
                elif target["metric"] == "power":
                    actual = positive(lap.avg_power)
                elif target["metric"] == "pace" and positive(lap.duration_sec) and positive(lap.distance_m):
                    scale = 100 if target["unit"] == "sec_per_100m" else 1000
                    actual = round(lap.duration_sec / lap.distance_m * scale, 3)
                values["target"] = {
                    **target,
                    "actual": actual,
                    "in_range": target["minimum"] <= actual <= target["maximum"] if actual is not None else None,
                }
            compared_laps.append(values)
    enough = any(row["delta"] is not None for row in summary) or any(
        row["measure"]["delta"] is not None for row in compared_laps
    )
    return {
        "status": "comparable" if enough else "insufficient_data",
        "summary": summary,
        "laps": compared_laps,
        "lap_alignment": "matched_count" if aligned else "ambiguous_or_missing",
        "quality": "partial"
        if (
            not aligned
            or any(x["actual"] is None for x in summary)
            or any(
                x["measure"]["actual"] is None or x.get("target", {}).get("actual", 1) is None for x in compared_laps
            )
        )
        else "good",
        "reason": "Comparación numérica; no certifica cumplimiento ni autoriza entrenamiento.",
    }


def daily_load_horizon(from_date, recorded_dates, now, timezone):
    """Continue deterministic decay through today, including days without records."""
    return max(from_date, now.astimezone(ZoneInfo(timezone)).date(), *recorded_dates)
