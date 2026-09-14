"""Contraseñas Argon2 y sesiones revocables con tokens opacos aleatorios."""
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import settings

hasher = PasswordHasher()
DUMMY_PASSWORD_HASH = hasher.hash(secrets.token_urlsafe(32))


def utcnow() -> datetime:
    return datetime.now(UTC)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def new_tokens() -> tuple[dict, dict]:
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    now = utcnow()
    return ({
        "access_hash": token_hash(access),
        "refresh_hash": token_hash(refresh),
        "access_expires_at": now + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES),
        "refresh_expires_at": now + timedelta(days=settings.REFRESH_TOKEN_DAYS),
    }, {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_MINUTES * 60,
    })
