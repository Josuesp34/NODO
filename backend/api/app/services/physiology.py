import math

import pandas as pd


def valid_number(value, minimum=0):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= minimum else None


def extract_session_metrics(df: pd.DataFrame, session: dict | None = None) -> dict:
    """Preferir resumen FIT; el intervalo entre registros es tiempo transcurrido."""
    session = session or {}
    timer = valid_number(session.get("total_timer_time"))
    elapsed = 0.0 if df.empty else (
        df["timestamp"].iloc[-1] - df["timestamp"].iloc[0]
    ).total_seconds()
    duration = timer if timer is not None else elapsed
    summary_hr = valid_number(session.get("avg_heart_rate"), minimum=1)
    hr = pd.to_numeric(df.get("heart_rate", pd.Series(dtype=float)), errors="coerce")
    hr = hr[hr.gt(0) & hr.map(math.isfinite)]
    avg_hr = summary_hr if summary_hr is not None else (float(hr.mean()) if not hr.empty else None)
    max_hr = valid_number(session.get("max_heart_rate"), minimum=1)
    if max_hr is None and not hr.empty:
        max_hr = float(hr.max())
    return {
        "avg_hr": avg_hr,
        "max_hr": int(max_hr) if max_hr is not None else None,
        "duration_min": duration / 60,
        "duration_source": "session_timer" if timer is not None else "record_elapsed",
        # No calcular carga con duración que incluye pausas o promedio de muestreo irregular.
        "trimp_inputs_available": timer is not None and summary_hr is not None,
    }
