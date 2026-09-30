from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from garmin_fit_sdk import Decoder, Stream
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.data_processing import clean_telemetry_to_dataframe
from app.services.physiology import extract_session_metrics, valid_number

router = APIRouter()


def sensor_value(row, name, fallback=None, integer=False, minimum=0):
    """Lee un sensor del registro FIT; la ausencia se conserva como nulo, no como cero."""
    value = valid_number(row.get(name), minimum=minimum)
    if value is None and fallback:
        value = valid_number(row.get(fallback), minimum=minimum)
    return int(value) if integer and value is not None else value


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
    """Ruta heredada cerrada: la ingesta exige identidad y dueño explícito."""
    del file, rest_hr, max_hr, is_male, db
    raise HTTPException(status_code=410, detail="Usa /athletes/{athlete_id}/activities/fit con sesión")
