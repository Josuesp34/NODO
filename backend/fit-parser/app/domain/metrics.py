"""Cálculos deterministas; no representan diagnósticos ni predicción de lesiones."""
import math


def _nonnegative(*values):
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("Se requieren valores finitos y no negativos")


def calculate_banister_trimp(
    duration_minutes: float,
    avg_hr: float,
    rest_hr: float,
    max_hr: float,
    is_male: bool,
) -> float:
    """Convención clásica: 0.64*exp(1.92*r) o 0.86*exp(1.67*r).

    Parámetros explícitos del atleta; la selección debe revisarse con el coach.
    """
    _nonnegative(duration_minutes, avg_hr, rest_hr, max_hr)
    if max_hr <= rest_hr or avg_hr > max_hr:
        raise ValueError("Revisar la frecuencia máxima y de reposo del atleta")
    if duration_minutes == 0 or avg_hr <= rest_hr:
        return 0.0
    ratio = (avg_hr - rest_hr) / (max_hr - rest_hr)
    factor, exponent = (0.64, 1.92) if is_male else (0.86, 1.67)
    return round(duration_minutes * ratio * factor * math.exp(exponent * ratio), 2)


def calculate_tss(duration_seconds: float, normalized_power: float, ftp: float) -> float:
    _nonnegative(duration_seconds, normalized_power, ftp)
    if ftp <= 0:
        raise ValueError("FTP debe ser mayor que cero")
    return round(duration_seconds / 3600 * (normalized_power / ftp) ** 2 * 100, 2)


def calculate_ewma(today_load: float, yesterday_ewma: float, time_constant: int) -> float:
    """Recurrencia diaria alpha=1/tau; conservar precisión entre días."""
    _nonnegative(today_load, yesterday_ewma)
    if not math.isfinite(time_constant) or time_constant < 1:
        raise ValueError("La constante temporal debe ser al menos un día")
    return yesterday_ewma + (today_load - yesterday_ewma) / time_constant


def calculate_training_status(
    today_load: float, yesterday_ctl: float, yesterday_atl: float
) -> dict[str, float]:
    """Una actualización por día local, sumando sesiones e incluyendo descansos.

    Convención: CTL/ATL al cierre del día, TSB al inicio. No calcula ACWR:
    ATL/CTL con ventanas 7/42 no implementa un cociente agudo/crónico 7/28.
    El consumidor debe suministrar estado histórico y una misma unidad de carga.
    """
    return {
        "ctl": calculate_ewma(today_load, yesterday_ctl, 42),
        "atl": calculate_ewma(today_load, yesterday_atl, 7),
        "tsb": yesterday_ctl - yesterday_atl,
    }
