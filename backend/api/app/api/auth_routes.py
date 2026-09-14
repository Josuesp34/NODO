from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_coach, current_session, current_user
from app.api.schemas import (
    ActivateAthlete,
    AthleteCreated,
    CoachRegistration,
    Identity,
    Login,
    RefreshRequest,
    TokenPair,
    UserView,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.security import DUMMY_PASSWORD_HASH, hash_password, new_tokens, token_hash, utcnow, verify_password
from app.infrastructure.database.models import AthleteInvitation, AuthSession, User
from app.infrastructure.database.models.user import UserRole

router = APIRouter(prefix="/auth", tags=["Auth"])


def user_view(user: User) -> UserView:
    return UserView.model_validate(user)


async def issue_session(db: AsyncSession, user: User) -> TokenPair:
    stored, response = new_tokens()
    db.add(AuthSession(user_id=user.id, **stored))
    await db.flush()
    return TokenPair(**response)


@router.post("/coaches", response_model=UserView, status_code=status.HTTP_201_CREATED)
async def register_coach(payload: CoachRegistration, db: AsyncSession = Depends(get_db)):
    """Solo bootstrap de desarrollo; producción necesita una ruta administrativa."""
    if settings.ENVIRONMENT != "development" or not settings.ALLOW_COACH_REGISTRATION:
        raise HTTPException(403, "El alta de entrenadores está cerrada")
    user = User(
        email=payload.email, first_name=payload.first_name, last_name=payload.last_name,
        timezone=payload.timezone, role=UserRole.COACH, hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "No se pudo crear la cuenta") from None
    await db.refresh(user)
    return user_view(user)


@router.post("/superusers", response_model=UserView, status_code=status.HTTP_201_CREATED)
async def register_superuser(
    payload: CoachRegistration,
    bootstrap_token: str | None = Header(default=None, alias="X-NODO-Development-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Bootstrap local, protegido por un secreto fuera de Git y deshabilitado por defecto."""
    if (
        settings.ENVIRONMENT != "development"
        or not settings.ALLOW_SUPERUSER_BOOTSTRAP
        or not settings.DEV_SUPERUSER_BOOTSTRAP_TOKEN
        or bootstrap_token != settings.DEV_SUPERUSER_BOOTSTRAP_TOKEN
    ):
        raise HTTPException(403, "El bootstrap de superusuarios está cerrado")
    user = User(
        email=payload.email, first_name=payload.first_name, last_name=payload.last_name,
        timezone=payload.timezone, role=UserRole.COACH, is_superuser=True,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "No se pudo crear la cuenta") from None
    await db.refresh(user)
    return user_view(user)


@router.post("/login", response_model=TokenPair)
async def login(payload: Login, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == str(payload.email).lower()))
    password_hash = user.hashed_password if user else DUMMY_PASSWORD_HASH
    if not verify_password(payload.password, password_hash) or user is None:
        raise HTTPException(401, "Correo o contraseña incorrectos", headers={"WWW-Authenticate": "Bearer"})
    tokens = await issue_session(db, user)
    await db.commit()
    return tokens


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    session = await db.scalar(select(AuthSession).where(
        AuthSession.refresh_hash == token_hash(payload.refresh_token), AuthSession.refresh_expires_at > utcnow()
    ))
    if session is None:
        raise HTTPException(401, "Sesión inválida o expirada", headers={"WWW-Authenticate": "Bearer"})
    user = await db.get(User, session.user_id)
    await db.delete(session)  # Rotar el token: uno usado no puede renovarse de nuevo.
    tokens = await issue_session(db, user)
    await db.commit()
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(session: AuthSession = Depends(current_session), db: AsyncSession = Depends(get_db)):
    await db.delete(session)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserView)
async def me(user: User = Depends(current_user)):
    return user_view(user)


@router.post("/athletes", response_model=AthleteCreated, status_code=status.HTTP_201_CREATED)
async def invite_athlete(payload: Identity, coach: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if coach.role != UserRole.COACH:
        raise HTTPException(403, "Esta acción requiere un entrenador")
    athlete = User(
        email=payload.email, first_name=payload.first_name, last_name=payload.last_name,
        timezone=payload.timezone, role=UserRole.ATHLETE, coach_id=coach.id, hashed_password="!pending!",
    )
    # Este token se usa solo para activación y se entrega temporalmente al caller de desarrollo.
    _, response = new_tokens()
    invitation_token = response["refresh_token"]
    db.add(athlete)
    await db.flush()
    invitation = AthleteInvitation(
        athlete_id=athlete.id, token_hash=token_hash(invitation_token),
        expires_at=utcnow() + timedelta(days=7),
    )
    db.add(invitation)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "No se pudo invitar al atleta") from None
    await db.refresh(athlete)
    return AthleteCreated(
        athlete=user_view(athlete), invitation_token=invitation_token, invitation_expires_at=invitation.expires_at,
    )


@router.get("/athletes", response_model=list[UserView])
async def list_athletes(coach: User = Depends(current_coach), db: AsyncSession = Depends(get_db)):
    result = await db.scalars(
        select(User)
        .where(User.coach_id == coach.id, User.role == UserRole.ATHLETE)
        .order_by(User.last_name, User.first_name, User.id)
    )
    return [user_view(athlete) for athlete in result.all()]


@router.post("/athletes/activate", response_model=TokenPair)
async def activate_athlete(payload: ActivateAthlete, db: AsyncSession = Depends(get_db)):
    invitation = await db.scalar(select(AthleteInvitation).where(
        AthleteInvitation.token_hash == token_hash(payload.invitation_token),
        AthleteInvitation.consumed_at.is_(None), AthleteInvitation.expires_at > utcnow(),
    ))
    if invitation is None:
        raise HTTPException(400, "Invitación inválida o expirada")
    athlete = await db.get(User, invitation.athlete_id)
    athlete.hashed_password = hash_password(payload.password)
    invitation.consumed_at = utcnow()
    tokens = await issue_session(db, athlete)
    await db.commit()
    return tokens
