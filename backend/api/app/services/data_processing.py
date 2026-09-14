import pandas as pd


def clean_telemetry_to_dataframe(record_data: list) -> pd.DataFrame:
    """Ordenar y normalizar registros sin inventar valores de sensores."""
    if not record_data:
        raise ValueError("El archivo no contiene telemetría")
    df = pd.DataFrame(record_data)
    df = df[[col for col in df.columns if not str(col).isnumeric()]]
    if "timestamp" not in df:
        raise ValueError("La telemetría no contiene timestamps")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    if df["timestamp"].isna().any():
        raise ValueError("La telemetría contiene timestamps inválidos")
    # Un registro por actividad e instante, conforme a la PK de telemetría.
    df = df.sort_values("timestamp", kind="stable").drop_duplicates("timestamp", keep="last")
    return df.reset_index(drop=True)
