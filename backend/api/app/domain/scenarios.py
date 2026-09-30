"""Explicit what-if arithmetic only: never an automatic plan or performance prediction."""

import math

from app.domain.metrics import calculate_training_status

FORMULA_VERSION = "ewma-42-7-v1"
LIMITS = [
    "Cada carga diaria es un supuesto del entrenador, incluido un descanso introducido como cero.",
    "CTL/ATL son promedios matemáticos en una misma unidad; TSB corresponde al inicio del día.",
    "No estima marca ni fecha de máximo rendimiento, ni autoriza entrenar o volver tras una molestia.",
    "No modifica ni publica sesiones. La revisión y cualquier cambio del calendario requieren otra acción.",
]


def project_loads(loads, initial_ctl, initial_atl):
    if any(not math.isfinite(value) or value < 0 or value > 100000 for value in loads):
        raise ValueError("Cada día requiere carga finita, no negativa y en la unidad elegida")
    ctl, atl = initial_ctl, initial_atl
    rows = []
    for value in loads:
        state = calculate_training_status(value, ctl, atl)
        ctl, atl = state["ctl"], state["atl"]
        rows.append({"load": value, **{key: round(number, 6) for key, number in state.items()}})
    return rows
