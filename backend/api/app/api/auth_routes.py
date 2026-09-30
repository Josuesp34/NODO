import re
import secrets
from datetime import UTC, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_coach, current_session, current_superuser, current_user
from app.api.schemas import (
    ActivateAthlete,
    AthleteCreated,
    CoachRegistration,
    Identity,
    Login,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    TokenPair,
    UserView,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.security import DUMMY_PASSWORD_HASH, hash_password, new_tokens, token_hash, utcnow, verify_password
from app.infrastructure.database.models import AthleteInvitation, AuthSession, PasswordReset, User
from app.infrastructure.database.models.product import (
    CoachAthleteAssignment,
    Organization,
    OrganizationMembership,
    UserRoleAssignment,
)
from app.infrastructure.database.models.user import UserRole
from app.services.access import (
    capabilities_for,
    enforce_athlete_capacity,
    organization_ids_for,
    primary_organization_id,
    roles_for,
)
from app.services.audit import add_audit
from app.services.email import email_ready, queue_email, require_email_ready
from app.services.rate_limit import clear_auth_failures, enforce_auth_rate_limit, register_auth_failure

router = APIRouter(prefix="/auth", tags=["Auth"])


async def user_view(db: AsyncSession, user: User) -> UserView:
    return UserView(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        timezone=user.timezone,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        coach_id=user.coach_id,
        is_superuser=user.is_superuser,
        roles=await roles_for(db, user.id),
        capabilities=await capabilities_for(db, user),
        organization_ids=await organization_ids_for(db, user.id),
    )


def organization_slug(email: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", email.split("@", 1)[0].lower()).strip("-") or "coach"
    return f"{stem}-{secrets.token_hex(3)}"


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
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        timezone=payload.timezone,
        role=UserRole.COACH,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        await db.flush()
        db.add(UserRoleAssignment(user_id=user.id, role="coach"))
        organization = Organization(name=f"{user.first_name} {user.last_name}", slug=organization_slug(user.email))
        db.add(organization)
        await db.flush()
        db.add(OrganizationMembership(organization_id=organization.id, user_id=user.id, role="owner", status="active"))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "No se pudo crear la cuenta") from None
    await db.refresh(user)
    return await user_view(db, user)


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
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        timezone=payload.timezone,
        role=UserRole.COACH,
        is_superuser=True,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        await db.flush()
        db.add(UserRoleAssignment(user_id=user.id, role="coach"))
        organization = Organization(name=f"{user.first_name} {user.last_name}", slug=organization_slug(user.email))
        db.add(organization)
        await db.flush()
        db.add(OrganizationMembership(organization_id=organization.id, user_id=user.id, role="owner", status="active"))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "No se pudo crear la cuenta") from None
    await db.refresh(user)
    return await user_view(db, user)


@router.post("/login", response_model=TokenPair)
async def login(payload: Login, db: AsyncSession = Depends(get_db)):
    email = str(payload.email).lower()
    await enforce_auth_rate_limit(db, "login", email)
    user = await db.scalar(select(User).where(User.email == email))
    password_hash = user.hashed_password if user else DUMMY_PASSWORD_HASH
    if not verify_password(payload.password, password_hash) or user is None or user.deleted_at is not None:
        await register_auth_failure(db, "login", email)
        raise HTTPException(401, "Correo o contraseña incorrectos", headers={"WWW-Authenticate": "Bearer"})
    await clear_auth_failures(db, "login", email)
    tokens = await issue_session(db, user)
    await db.commit()
    return tokens


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    refresh_key = token_hash(payload.refresh_token)
    await enforce_auth_rate_limit(db, "refresh", refresh_key)
    session = await db.scalar(
        select(AuthSession)
        .where(
            AuthSession.refresh_hash == refresh_key,
            AuthSession.refresh_expires_at > utcnow(),
        )
        .with_for_update()
    )
    if session is None:
        await register_auth_failure(db, "refresh", refresh_key)
        raise HTTPException(401, "Sesión inválida o expirada", headers={"WWW-Authenticate": "Bearer"})
    await clear_auth_failures(db, "refresh", refresh_key)
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
async def me(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await user_view(db, user)


@router.get("/identity", response_model=UserView)
async def identity(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await user_view(db, user)


@router.post("/athletes", response_model=AthleteCreated, status_code=status.HTTP_201_CREATED)
async def invite_athlete(payload: Identity, coach: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if "coach" not in await roles_for(db, coach.id) and not coach.is_superuser:
        raise HTTPException(403, "Esta acción requiere un entrenador")
    if settings.ENVIRONMENT != "development":
        require_email_ready()
    organization_id = await primary_organization_id(db, coach.id)
    await enforce_athlete_capacity(db, coach.id, organization_id)
    athlete = User(
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        timezone=payload.timezone,
        role=UserRole.ATHLETE,
        coach_id=coach.id,
        hashed_password="!pending!",
    )
    # Este token se usa solo para activación y se entrega temporalmente al caller de desarrollo.
    _, response = new_tokens()
    invitation_token = response["refresh_token"]
    db.add(athlete)
    await db.flush()
    db.add(UserRoleAssignment(user_id=athlete.id, role="athlete"))
    db.add(
        CoachAthleteAssignment(
            organization_id=organization_id,
            coach_id=coach.id,
            athlete_id=athlete.id,
            status="active",
        )
    )
    db.add(OrganizationMembership(organization_id=organization_id, user_id=athlete.id, role="athlete", status="active"))
    invitation = AthleteInvitation(
        athlete_id=athlete.id,
        token_hash=token_hash(invitation_token),
        expires_at=utcnow() + timedelta(days=7),
    )
    db.add(invitation)
    await db.flush()
    if email_ready():
        queue_email(
            db,
            recipient=athlete.email,
            subject="Activa tu cuenta NODO",
            body=(
                f"Hola {athlete.first_name},\n\n"
                f"Tu entrenador te invitó a NODO. Abre {settings.PUBLIC_APP_URL.rstrip('/')}/activate "
                "y pega este código de un solo uso:\n\n"
                f"{invitation_token}\n\n"
                "Caduca en 7 días. Si no esperabas esta invitación, ignora este correo."
            ),
            dedupe_key=f"nodo-invitation-{invitation.id}",
        )
    add_audit(
        db,
        actor_id=coach.id,
        entity="athlete_invitation",
        entity_id=athlete.id,
        action="create",
        after={"organization_id": organization_id},
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "No se pudo invitar al atleta") from None
    await db.refresh(athlete)
    return AthleteCreated(
        athlete=await user_view(db, athlete),
        invitation_token=invitation_token if settings.ENVIRONMENT == "development" and not email_ready() else None,
        invitation_expires_at=invitation.expires_at,
    )


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(payload: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    require_email_ready()
    email = str(payload.email).lower()
    await enforce_auth_rate_limit(db, "password-reset-request", email)
    # El mismo límite se aplica a direcciones existentes y no existentes.
    await register_auth_failure(db, "password-reset-request", email)
    user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)).with_for_update())
    if user is None:
        return {"detail": "Si existe una cuenta, enviaremos instrucciones a ese correo."}
    latest = await db.scalar(
        select(PasswordReset).where(PasswordReset.user_id == user.id).order_by(PasswordReset.created_at.desc()).limit(1)
    )
    latest_created_at = (
        latest.created_at
        if latest and latest.created_at.tzinfo
        else (latest.created_at.replace(tzinfo=UTC) if latest else None)
    )
    if latest_created_at and utcnow() - latest_created_at < timedelta(minutes=15):
        return {"detail": "Si existe una cuenta, enviaremos instrucciones a ese correo."}
    code = secrets.token_urlsafe(32)
    reset = PasswordReset(user_id=user.id, token_hash=token_hash(code), expires_at=utcnow() + timedelta(minutes=30))
    db.add(reset)
    await db.flush()
    queue_email(
        db,
        recipient=user.email,
        subject="Recupera tu acceso a NODO",
        body=(
            "Recibimos una solicitud para cambiar tu contraseña. "
            f"Abre {settings.PUBLIC_APP_URL.rstrip('/')}/password-reset y pega este código:\n\n"
            f"{code}\n\n"
            "Caduca en 30 minutos. Si no hiciste esta solicitud, ignora el correo."
        ),
        dedupe_key=f"nodo-password-reset-{reset.id}",
    )
    await db.commit()
    return {"detail": "Si existe una cuenta, enviaremos instrucciones a ese correo."}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(payload: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    code_hash = token_hash(payload.reset_token)
    email = str(payload.email).lower()
    await enforce_auth_rate_limit(db, "password-reset-confirm", email)
    reset = await db.scalar(
        select(PasswordReset)
        .join(User, User.id == PasswordReset.user_id)
        .where(
            PasswordReset.token_hash == code_hash,
            User.email == email,
            User.deleted_at.is_(None),
        )
        .with_for_update()
    )
    expires_at = (
        reset.expires_at
        if reset and reset.expires_at.tzinfo
        else (reset.expires_at.replace(tzinfo=UTC) if reset else None)
    )
    if reset is None or reset.consumed_at is not None or expires_at <= utcnow():
        await register_auth_failure(db, "password-reset-confirm", email)
        raise HTTPException(400, "Código inválido o expirado")
    user = await db.get(User, reset.user_id)
    user.hashed_password = hash_password(payload.password)
    user.email_verified_at = utcnow()
    await db.execute(update(PasswordReset).where(PasswordReset.user_id == user.id).values(consumed_at=utcnow()))
    await db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    await clear_auth_failures(db, "password-reset-confirm", email)
    add_audit(db, actor_id=user.id, entity="auth", entity_id=user.id, action="password_reset")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/athletes", response_model=list[UserView])
async def list_athletes(coach: User = Depends(current_coach), db: AsyncSession = Depends(get_db)):
    result = await db.scalars(
        select(User)
        .join(CoachAthleteAssignment, CoachAthleteAssignment.athlete_id == User.id)
        .where(
            CoachAthleteAssignment.coach_id == coach.id,
            CoachAthleteAssignment.status == "active",
            User.deleted_at.is_(None),
        )
        .order_by(User.last_name, User.first_name, User.id)
    )
    return [await user_view(db, athlete) for athlete in result.all()]


@router.post("/athletes/activate", response_model=TokenPair)
async def activate_athlete(payload: ActivateAthlete, db: AsyncSession = Depends(get_db)):
    invitation_key = token_hash(payload.invitation_token)
    await enforce_auth_rate_limit(db, "activation", invitation_key)
    invitation = await db.scalar(
        select(AthleteInvitation).where(
            AthleteInvitation.token_hash == invitation_key,
            AthleteInvitation.consumed_at.is_(None),
            AthleteInvitation.expires_at > utcnow(),
        )
    )
    if invitation is None:
        await register_auth_failure(db, "activation", invitation_key)
        raise HTTPException(400, "Invitación inválida o expirada")
    await clear_auth_failures(db, "activation", invitation_key)
    athlete = await db.get(User, invitation.athlete_id)
    athlete.hashed_password = hash_password(payload.password)
    athlete.email_verified_at = utcnow()
    invitation.consumed_at = utcnow()
    tokens = await issue_session(db, athlete)
    await db.commit()
    return tokens


@router.delete("/athletes/{athlete_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_athlete_assignment(
    athlete_id: int,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    assignment = await db.scalar(
        select(CoachAthleteAssignment).where(
            CoachAthleteAssignment.coach_id == coach.id,
            CoachAthleteAssignment.athlete_id == athlete_id,
            CoachAthleteAssignment.status == "active",
        )
    )
    if assignment is None:
        raise HTTPException(404, "Atleta no encontrado")
    assignment.status = "revoked"
    assignment.revoked_at = utcnow()
    add_audit(
        db,
        actor_id=coach.id,
        entity="coach_athlete_assignment",
        entity_id=assignment.id,
        action="revoke",
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/users/{user_id}/roles/{role}", status_code=status.HTTP_204_NO_CONTENT)
async def grant_role(
    user_id: int,
    role: str,
    admin: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_db),
):
    if role not in {"coach", "athlete"}:
        raise HTTPException(422, "Rol no soportado")
    target = await db.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise HTTPException(404, "Usuario no encontrado")
    existing = await db.scalar(
        select(UserRoleAssignment.id).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role == role,
        )
    )
    if existing is None:
        db.add(UserRoleAssignment(user_id=user_id, role=role))
        add_audit(
            db,
            actor_id=admin.id,
            entity="user_role",
            entity_id=user_id,
            action="grant",
            after={"role": role},
        )
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
