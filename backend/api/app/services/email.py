"""Transactional email outbox. No recipient or token is stored in clear text."""

from datetime import UTC, datetime

import httpx
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.database.models.product import Job


def _cipher() -> Fernet:
    try:
        return Fernet(settings.EMAIL_QUEUE_KEY.encode())
    except (ValueError, TypeError) as exc:
        raise RuntimeError("EMAIL_QUEUE_KEY no es una clave Fernet válida") from exc


def email_ready() -> bool:
    if not settings.RESEND_API_KEY or not settings.RESEND_FROM_EMAIL or not settings.EMAIL_QUEUE_KEY:
        return False
    if "@" not in settings.RESEND_FROM_EMAIL:
        return False
    if settings.ENVIRONMENT != "development" and not settings.PUBLIC_APP_URL.startswith("https://"):
        return False
    try:
        _cipher()
    except RuntimeError:
        return False
    return True


def require_email_ready() -> None:
    if not email_ready():
        raise HTTPException(503, "El correo transaccional aún no está configurado")


def queue_email(db: AsyncSession, *, recipient: str, subject: str, body: str, dedupe_key: str) -> None:
    require_email_ready()
    # El cifrado se hace antes de escribir la transacción; ningún código ni
    # destinatario de recuperación queda visible en la tabla de trabajos.
    import json

    encrypted = _cipher().encrypt(json.dumps({"to": recipient, "subject": subject, "text": body}).encode())
    db.add(
        Job(
            kind="send_resend_email",
            payload={"ciphertext": encrypted.decode()},
            run_after=datetime.now(UTC),
            max_attempts=settings.JOB_MAX_ATTEMPTS,
            status="pending",
            dedupe_key=dedupe_key,
        )
    )


async def send_queued_email(job: Job) -> None:
    import json

    if not email_ready():
        raise RuntimeError("Correo transaccional no configurado en el worker")
    message = json.loads(_cipher().decrypt(job.payload["ciphertext"].encode()))
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Idempotency-Key": job.dedupe_key or f"nodo-email-{job.id}",
            },
            json={"from": settings.RESEND_FROM_EMAIL, **message},
        )
    if not 200 <= response.status_code < 300:
        # No incluir respuesta de proveedor: podría contener dirección o contenido.
        raise RuntimeError(f"Resend rechazó el envío (HTTP {response.status_code})")
