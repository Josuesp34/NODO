from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import token_hash, utcnow
from app.infrastructure.database.models import AuthSession, User
from app.infrastructure.database.models.user import UserRole

bearer = HTTPBearer(auto_error=False)


def unauthorized() -> HTTPException:
    return HTTPException(401, "Sesión inválida o expirada", headers={"WWW-Authenticate": "Bearer"})


async def current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> AuthSession:
    if credentials is None:
        raise unauthorized()
    session = await db.scalar(select(AuthSession).where(
        AuthSession.access_hash == token_hash(credentials.credentials),
        AuthSession.access_expires_at > utcnow(),
        AuthSession.refresh_expires_at > utcnow(),
    ))
    if session is None:
        raise unauthorized()
    return session


async def current_user(
    session: AuthSession = Depends(current_session), db: AsyncSession = Depends(get_db),
) -> User:
    user = await db.get(User, session.user_id)
    if user is None:
        raise unauthorized()
    return user


async def current_coach(user: User = Depends(current_user)) -> User:
    if user.role != UserRole.COACH:
        raise HTTPException(403, "Esta acción requiere un entrenador")
    return user


async def current_superuser(user: User = Depends(current_user)) -> User:
    if not user.is_superuser:
        raise HTTPException(403, "Esta acción requiere un superusuario")
    return user


async def accessible_athlete(db: AsyncSession, user: User, athlete_id: int) -> User:
    query = select(User).where(User.id == athlete_id, User.role == UserRole.ATHLETE)
    if user.role == UserRole.COACH:
        query = query.where(User.coach_id == user.id)
    else:
        query = query.where(User.id == user.id)
    athlete = await db.scalar(query)
    if athlete is None:
        raise HTTPException(404, "Atleta no encontrado")
    return athlete
