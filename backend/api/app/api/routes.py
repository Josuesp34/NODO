from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from garmin_fit_sdk import Decoder, Stream
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.database import get_db
from app.domain.metrics import calculate_banister_trimp
from app.infrastructure.database.models import Activity, TelemetryRecord
from app.services.data_processing import clean_telemetry_to_dataframe
from app.services.physiology import extract_session_metrics, valid_number

router = APIRouter()


def parse_fit(content: bytes):
    """Trabajo CPU fuera del event loop; multisesión pendiente de segmentación."""
    try:
        decoder = Decoder(Stream.from_byte_array(bytearray(content)))
        if not decoder.is_fit():
            raise ValueError("El binario no es FIT")
        messages, errors = decoder.read()
        if errors:
            raise ValueError("El archivo FIT contiene errores de decodificación")
        sessions = messages.get("session_mesgs", [])
        if len(sessions) > 1:
            raise ValueError("FIT multisesión aún no soportado; importar una disciplina por archivo")
        df = clean_telemetry_to_dataframe(messages.get("record_mesgs", []))
        return df, extract_session_metrics(df, sessions[0] if sessions else None)
    except ValueError:
        raise
    except Exception:
        raise ValueError("No se pudo decodificar el archivo FIT") from None


@router.post("/upload-fit/")
async def upload_fit_file(
    file: UploadFile = File(...),
    rest_hr: float | None = Form(default=None, gt=0),
    max_hr: float | None = Form(default=None, gt=0),
    is_male: bool | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Prototipo LOCAL sin identidad: no exponer a atletas antes de implementar auth."""
    if settings.ENVIRONMENT != "development":
        raise HTTPException(status_code=503, detail="Ingesta deshabilitada hasta implementar autenticación")
    if not file.filename or not file.filename.lower().endswith(".fit"):
        raise HTTPException(status_code=400, detail="Extensión inválida, debe ser .fit")
    content = await file.read(settings.MAX_FIT_BYTES + 1)
    if len(content) > settings.MAX_FIT_BYTES:
        raise HTTPException(status_code=413, detail="Archivo FIT demasiado grande")
    try:
        df, metrics = await run_in_threadpool(parse_fit, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    provided = (rest_hr is not None, max_hr is not None, is_male is not None)
    if any(provided) and not all(provided):
        raise HTTPException(status_code=422, detail="Proporcionar rest_hr, max_hr e is_male juntos")
    trimp_value = None
    if all(provided):
        try:
            # Validar configuración incluso si el FIT no contiene datos suficientes.
            calculate_banister_trimp(0, 0, rest_hr, max_hr, is_male)
            if metrics["trimp_inputs_available"]:
                trimp_value = calculate_banister_trimp(
                    metrics["duration_min"], metrics["avg_hr"], rest_hr, max_hr, is_male
                )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    try:
        activity = Activity(
            file_name=file.filename,
            start_time=df["timestamp"].iloc[0].to_pydatetime(),
            total_duration_sec=metrics["duration_min"] * 60,
            avg_heart_rate=round(metrics["avg_hr"]) if metrics["avg_hr"] is not None else None,
            max_heart_rate=metrics["max_hr"],
            calculated_trimp=trimp_value,
        )
        db.add(activity)
        await db.flush()
        telemetry = []
        for _, row in df.iterrows():
            def sensor(name, fallback=None, integer=False, minimum=0):
                value = valid_number(row.get(name), minimum=minimum)
                if value is None and fallback:
                    value = valid_number(row.get(fallback), minimum=minimum)
                return int(value) if integer and value is not None else value

            telemetry.append(TelemetryRecord(
                activity_id=activity.id,
                timestamp=row["timestamp"].to_pydatetime(),
                heart_rate=sensor("heart_rate", integer=True, minimum=1),
                altitude=sensor("enhanced_altitude", "altitude", minimum=-15000),
                speed_ms=sensor("enhanced_speed", "speed"),
                cadence=sensor("cadence", integer=True),
                power=sensor("power", integer=True),
                temperature=sensor("temperature", integer=True, minimum=-100),
            ))
        db.add_all(telemetry)
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo guardar la actividad") from None

    return {
        "status": "Actividad importada en el entorno de desarrollo",
        "activity_id": activity.id,
        "session_analytics": {
            "duration_minutes": round(metrics["duration_min"], 2),
            "duration_source": metrics["duration_source"],
            "avg_heart_rate": metrics["avg_hr"],
            "trimp_score": trimp_value,
            "trimp_status": "calculated" if trimp_value is not None else "insufficient_inputs",
            "telemetry_points_saved": len(telemetry),
        },
    }
