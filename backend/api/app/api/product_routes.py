import secrets
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_coach, current_superuser, current_user
from app.api.planning_routes import check_block
from app.api.product_schemas import (
    CheckinUpsert,
    CheckinView,
    CompetitionCreate,
    CompetitionView,
    ComplaintCreate,
    ComplaintUpdateCreate,
    ComplaintView,
    ConnectionRequest,
    ConnectionView,
    ConsentGrant,
    ConsentView,
    DeleteAccount,
    GroupCreate,
    GroupMemberCreate,
    GroupMemberView,
    GroupView,
    ObservationCreate,
    ObservationView,
    PaymentCreate,
    PlanCreate,
    ProfileUpsert,
    ProfileView,
    RecommendationCreate,
    RecommendationDecision,
    RecommendationView,
    ReviewDecision,
    ReviewItemView,
    SubscriptionCreate,
    TemplateApply,
    TemplateCreate,
    TemplateView,
    WorkoutChanges,
)
from app.api.schemas import WorkoutCreate
from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password, utcnow, verify_password
from app.infrastructure.database.models import Activity, AuthSession, PrescribedWorkout, TrainingBlock, User
from app.infrastructure.database.models.product import (
    AssistantConfirmation,
    AssistantMessage,
    AssistantThread,
    AthleteConnection,
    AthleteGroup,
    AthleteProfile,
    Checkin,
    CoachAthleteAssignment,
    CommercialPlan,
    Competition,
    Complaint,
    ComplaintUpdate,
    Consent,
    DailyLoad,
    Decision,
    GroupMembership,
    ManagedPayment,
    Observation,
    OrganizationMembership,
    PlanAssignment,
    PlanTemplate,
    Recommendation,
    ReviewItem,
    Subscription,
    UserRoleAssignment,
)
from app.services.access import has_athlete_access, primary_organization_id, require_athlete_access
from app.services.assistant import assistant_message_view, require_assistant_thread_access
from app.services.audit import add_audit

router = APIRouter(tags=["Pilot product"])


def serialize_steps(value) -> list[dict]:
    return [group.model_dump(mode="json") for group in value]


@router.put("/athletes/{athlete_id}/profile", response_model=ProfileView)
async def upsert_profile(
    athlete_id: int,
    payload: ProfileUpsert,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, user, athlete_id)
    if user.id == athlete_id and not user.is_superuser:
        raise HTTPException(403, "El entrenador administra los parámetros fisiológicos")
    current = await db.scalar(
        select(AthleteProfile).where(
            AthleteProfile.athlete_id == athlete_id,
            AthleteProfile.valid_to.is_(None),
        )
    )
    if current is not None:
        if payload.valid_from <= current.valid_from:
            raise HTTPException(409, "La nueva vigencia debe iniciar después del perfil actual")
        current.valid_to = payload.valid_from
    profile = AthleteProfile(athlete_id=athlete_id, **payload.model_dump())
    db.add(profile)
    await db.flush()
    add_audit(
        db,
        actor_id=user.id,
        entity="athlete_profile",
        entity_id=profile.id,
        action="version",
        after=payload.model_dump(mode="json"),
    )
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/athletes/{athlete_id}/profile", response_model=ProfileView)
async def get_profile(
    athlete_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, user, athlete_id)
    profile = await db.scalar(
        select(AthleteProfile)
        .where(AthleteProfile.athlete_id == athlete_id, AthleteProfile.valid_to.is_(None))
        .order_by(AthleteProfile.valid_from.desc())
    )
    if profile is None:
        raise HTTPException(404, "Perfil no configurado")
    return profile


@router.post(
    "/athletes/{athlete_id}/competitions",
    response_model=CompetitionView,
    status_code=status.HTTP_201_CREATED,
)
async def create_competition(
    athlete_id: int,
    payload: CompetitionCreate,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, coach, athlete_id)
    competition = Competition(athlete_id=athlete_id, coach_id=coach.id, **payload.model_dump())
    db.add(competition)
    await db.flush()
    add_audit(
        db,
        actor_id=coach.id,
        entity="competition",
        entity_id=competition.id,
        action="create",
        after=payload.model_dump(mode="json"),
    )
    await db.commit()
    await db.refresh(competition)
    return competition


@router.get("/athletes/{athlete_id}/competitions", response_model=list[CompetitionView])
async def list_competitions(
    athlete_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, user, athlete_id)
    rows = await db.scalars(
        select(Competition).where(Competition.athlete_id == athlete_id).order_by(Competition.competition_date)
    )
    return rows.all()


@router.post(
    "/athletes/{athlete_id}/observations",
    response_model=ObservationView,
    status_code=status.HTTP_201_CREATED,
)
async def create_observation(
    athlete_id: int,
    payload: ObservationCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, user, athlete_id)
    observation = Observation(
        athlete_id=athlete_id,
        received_at=datetime.now(UTC),
        **payload.model_dump(),
    )
    db.add(observation)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(
            select(Observation).where(
                Observation.athlete_id == athlete_id,
                Observation.source == payload.source,
                Observation.external_id == payload.external_id,
                Observation.observed_start == payload.observed_start,
            )
        )
        if existing is None:
            raise HTTPException(409, "Observación duplicada") from None
        return existing
    await db.refresh(observation)
    return observation


@router.get("/athletes/{athlete_id}/observations", response_model=list[ObservationView])
async def list_observations(
    athlete_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, user, athlete_id)
    rows = await db.scalars(
        select(Observation)
        .where(Observation.athlete_id == athlete_id)
        .order_by(Observation.observed_start.desc())
        .limit(500)
    )
    return rows.all()


@router.put("/athletes/{athlete_id}/checkins/{local_date}", response_model=CheckinView)
async def upsert_checkin(
    athlete_id: int,
    local_date: str,
    payload: CheckinUpsert,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, user, athlete_id)
    if user.id != athlete_id and not user.is_superuser:
        raise HTTPException(403, "Sólo el atleta registra sus sensaciones")
    if str(payload.local_date) != local_date:
        raise HTTPException(422, "La fecha del cuerpo no coincide con la URL")
    checkin = await db.scalar(
        select(Checkin).where(Checkin.athlete_id == athlete_id, Checkin.local_date == payload.local_date)
    )
    if checkin is None:
        checkin = Checkin(athlete_id=athlete_id, **payload.model_dump())
        db.add(checkin)
    else:
        for key, value in payload.model_dump().items():
            setattr(checkin, key, value)
    await db.commit()
    await db.refresh(checkin)
    return checkin


async def open_complaint_review(db: AsyncSession, complaint: Complaint, priority: str, reason: str) -> None:
    dedupe_key = f"complaint:{complaint.id}"
    item = await db.scalar(select(ReviewItem).where(ReviewItem.dedupe_key == dedupe_key))
    if item is None:
        db.add(
            ReviewItem(
                athlete_id=complaint.athlete_id,
                complaint_id=complaint.id,
                kind="complaint",
                priority=priority,
                reason=reason,
                dedupe_key=dedupe_key,
                status="open",
            )
        )
    else:
        item.priority = priority
        item.reason = reason
        item.status = "open"
        item.decided_by = None
        item.decision_note = None


@router.post(
    "/athletes/{athlete_id}/complaints",
    response_model=ComplaintView,
    status_code=status.HTTP_201_CREATED,
)
async def create_complaint(
    athlete_id: int,
    payload: ComplaintCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, user, athlete_id)
    if user.id != athlete_id and not user.is_superuser:
        raise HTTPException(403, "Sólo el atleta reporta una molestia")
    complaint = Complaint(athlete_id=athlete_id, **payload.model_dump())
    db.add(complaint)
    await db.flush()
    await open_complaint_review(
        db,
        complaint,
        "high" if payload.limits_movement or payload.intensity_0_10 >= 7 else "normal",
        "Molestia nueva reportada por el atleta",
    )
    add_audit(
        db,
        actor_id=user.id,
        entity="complaint",
        entity_id=complaint.id,
        action="report",
        after={"intensity_0_10": complaint.intensity_0_10, "limits_movement": complaint.limits_movement},
    )
    await db.commit()
    await db.refresh(complaint)
    return complaint


@router.post("/complaints/{complaint_id}/updates", response_model=ComplaintView)
async def update_complaint(
    complaint_id: int,
    payload: ComplaintUpdateCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    complaint = await db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(404, "Molestia no encontrada")
    await require_athlete_access(db, user, complaint.athlete_id)
    if user.id != complaint.athlete_id and not user.is_superuser:
        raise HTTPException(403, "Sólo el atleta actualiza su molestia")
    worsened = payload.intensity_0_10 > complaint.intensity_0_10 or (
        payload.limits_movement and not complaint.limits_movement
    )
    db.add(ComplaintUpdate(complaint_id=complaint.id, actor_id=user.id, **payload.model_dump()))
    complaint.intensity_0_10 = payload.intensity_0_10
    complaint.limits_movement = payload.limits_movement
    complaint.note = payload.note
    if worsened or complaint.status == "closed":
        complaint.status = "reported"
        await open_complaint_review(db, complaint, "high" if worsened else "normal", "La molestia empeoró o se reabrió")
    await db.commit()
    await db.refresh(complaint)
    return complaint


@router.get("/athletes/{athlete_id}/complaints", response_model=list[ComplaintView])
async def list_complaints(
    athlete_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, user, athlete_id)
    rows = await db.scalars(
        select(Complaint).where(Complaint.athlete_id == athlete_id).order_by(Complaint.created_at.desc())
    )
    return rows.all()


@router.get("/review-items", response_model=list[ReviewItemView])
async def review_inbox(coach: User = Depends(current_coach), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(
        select(ReviewItem)
        .join(CoachAthleteAssignment, CoachAthleteAssignment.athlete_id == ReviewItem.athlete_id)
        .where(
            CoachAthleteAssignment.coach_id == coach.id,
            CoachAthleteAssignment.status == "active",
            ReviewItem.status.in_(["open", "follow_up"]),
        )
        .order_by(ReviewItem.priority.desc(), ReviewItem.created_at)
    )
    return rows.all()


@router.post("/review-items/{item_id}/decision", response_model=ReviewItemView)
async def decide_review(
    item_id: int,
    payload: ReviewDecision,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(ReviewItem, item_id)
    if item is None:
        raise HTTPException(404, "Caso no encontrado")
    await require_athlete_access(db, coach, item.athlete_id)
    item.status = payload.status
    item.decided_by = coach.id
    item.decision_note = payload.note
    if item.complaint_id:
        complaint = await db.get(Complaint, item.complaint_id)
        if complaint is not None:
            complaint.status = payload.status
    add_audit(
        db,
        actor_id=coach.id,
        entity="review_item",
        entity_id=item.id,
        action=payload.status,
        after={"note": payload.note},
    )
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/groups", response_model=GroupView, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    group = AthleteGroup(
        organization_id=await primary_organization_id(db, coach.id), coach_id=coach.id, name=payload.name
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.get("/groups", response_model=list[GroupView])
async def list_groups(
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(AthleteGroup).where(AthleteGroup.coach_id == coach.id).order_by(AthleteGroup.name, AthleteGroup.id)
    )
    return rows.all()


@router.post("/groups/{group_id}/members", status_code=status.HTTP_201_CREATED)
async def add_group_member(
    group_id: int,
    payload: GroupMemberCreate,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    group = await db.scalar(select(AthleteGroup).where(AthleteGroup.id == group_id, AthleteGroup.coach_id == coach.id))
    if group is None:
        raise HTTPException(404, "Grupo no encontrado")
    await require_athlete_access(db, coach, payload.athlete_id)
    member = GroupMembership(group_id=group_id, **payload.model_dump())
    db.add(member)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "El atleta ya pertenece al grupo") from None
    return {"id": member.id, "group_id": group_id, **payload.model_dump()}


@router.get("/groups/{group_id}/members", response_model=list[GroupMemberView])
async def list_group_members(
    group_id: int,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    group = await db.scalar(select(AthleteGroup).where(AthleteGroup.id == group_id, AthleteGroup.coach_id == coach.id))
    if group is None:
        raise HTTPException(404, "Grupo no encontrado")
    rows = await db.scalars(
        select(GroupMembership).where(GroupMembership.group_id == group_id).order_by(GroupMembership.athlete_id)
    )
    return rows.all()


@router.post("/templates", response_model=TemplateView, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: TemplateCreate,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    for workout in payload.workouts:
        candidate = {key: value for key, value in workout.items() if key != "key"}
        WorkoutCreate.model_validate({**candidate, "sport_type": candidate.get("sport_type", payload.sport_type)})
    template = PlanTemplate(
        organization_id=await primary_organization_id(db, coach.id),
        coach_id=coach.id,
        **payload.model_dump(),
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.get("/templates", response_model=list[TemplateView])
async def list_templates(
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(PlanTemplate).where(PlanTemplate.coach_id == coach.id).order_by(PlanTemplate.name, PlanTemplate.id)
    )
    return rows.all()


@router.post("/templates/{template_id}/apply")
async def apply_template(
    template_id: int,
    payload: TemplateApply,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    template = await db.scalar(
        select(PlanTemplate).where(PlanTemplate.id == template_id, PlanTemplate.coach_id == coach.id)
    )
    if template is None:
        raise HTTPException(404, "Plantilla no encontrada")
    created_workout_ids: list[int] = []
    for athlete_id in sorted(set(payload.athlete_ids)):
        await require_athlete_access(db, coach, athlete_id)
        overrides = payload.overrides.get(athlete_id, {})
        assignment = await db.scalar(
            select(PlanAssignment).where(
                PlanAssignment.template_id == template.id,
                PlanAssignment.athlete_id == athlete_id,
            )
        )
        if (
            assignment is not None
            and assignment.applied_version == template.version
            and assignment.overrides == overrides
        ):
            continue
        if assignment is None:
            assignment = PlanAssignment(
                template_id=template.id,
                athlete_id=athlete_id,
                overrides=overrides,
                applied_version=template.version,
            )
            db.add(assignment)
        else:
            assignment.overrides = overrides
            assignment.applied_version = template.version
        for raw in template.workouts:
            merged = {**raw, **overrides.get(str(raw.get("key", "")), {})}
            merged.pop("key", None)
            parsed = WorkoutCreate.model_validate(
                {**merged, "sport_type": merged.get("sport_type", template.sport_type)}
            )
            workout = PrescribedWorkout(
                athlete_id=athlete_id,
                coach_id=coach.id,
                title=parsed.title,
                description=parsed.description,
                scheduled_date=parsed.scheduled_date,
                sport_type=parsed.sport_type,
                block_id=parsed.block_id,
                steps=serialize_steps(parsed.steps),
            )
            db.add(workout)
            await db.flush()
            created_workout_ids.append(workout.id)
    await db.commit()
    return {"template_id": template.id, "workout_ids": created_workout_ids}


@router.post("/consents", response_model=ConsentView, status_code=status.HTTP_201_CREATED)
async def grant_consent(
    payload: ConsentGrant,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    consent = await db.scalar(
        select(Consent).where(
            Consent.user_id == user.id,
            Consent.scope == payload.scope,
            Consent.version == payload.version,
        )
    )
    if consent is None:
        consent = Consent(user_id=user.id, granted_at=datetime.now(UTC), **payload.model_dump())
        db.add(consent)
    else:
        consent.granted_at = datetime.now(UTC)
        consent.revoked_at = None
    await db.commit()
    await db.refresh(consent)
    return consent


@router.get("/consents", response_model=list[ConsentView])
async def list_consents(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(select(Consent).where(Consent.user_id == user.id).order_by(Consent.granted_at.desc()))
    return rows.all()


@router.delete("/consents/{consent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_consent(
    consent_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    consent = await db.scalar(select(Consent).where(Consent.id == consent_id, Consent.user_id == user.id))
    if consent is None:
        raise HTTPException(404, "Consentimiento no encontrado")
    consent.revoked_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/account/export")
async def export_account(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    activities = (
        await db.scalars(select(Activity).where(Activity.athlete_id == user.id).order_by(Activity.start_time))
    ).all()
    observations = (
        await db.scalars(
            select(Observation).where(Observation.athlete_id == user.id).order_by(Observation.observed_start)
        )
    ).all()
    checkins = (
        await db.scalars(select(Checkin).where(Checkin.athlete_id == user.id).order_by(Checkin.local_date))
    ).all()
    complaints = (
        await db.scalars(select(Complaint).where(Complaint.athlete_id == user.id).order_by(Complaint.id))
    ).all()
    messages = (
        await db.execute(
            select(AssistantMessage, AssistantThread)
            .join(AssistantThread, AssistantThread.id == AssistantMessage.thread_id)
            .where(AssistantThread.owner_id == user.id)
            .order_by(AssistantMessage.created_at, AssistantMessage.id)
        )
    ).all()
    assistant_messages = []
    for message, thread in messages:
        try:
            await require_assistant_thread_access(db, user, thread)
        except HTTPException as exc:
            if exc.status_code not in {403, 404}:
                raise
            continue
        visible = await assistant_message_view(db, user, message)
        assistant_messages.append({key: visible[key] for key in ("author", "content", "created_at")})
    return {
        "generated_at": datetime.now(UTC),
        "user": {"id": user.id, "email": user.email, "timezone": user.timezone},
        "activities": [
            {
                "id": item.id,
                "provider": item.provider,
                "sport_type": item.sport_type,
                "started_at": item.start_time,
                "duration_sec": item.total_duration_sec,
            }
            for item in activities
        ],
        "observations": [ObservationView.model_validate(item).model_dump(mode="json") for item in observations],
        "checkins": [CheckinView.model_validate(item).model_dump(mode="json") for item in checkins],
        "complaints": [ComplaintView.model_validate(item).model_dump(mode="json") for item in complaints],
        "assistant_messages": assistant_messages,
    }


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    payload: DeleteAccount,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(401, "Contraseña incorrecta")
    add_audit(db, actor_id=user.id, entity="user", entity_id=user.id, action="deidentify")
    thread_ids = select(AssistantThread.id).where(AssistantThread.owner_id == user.id)
    await db.execute(delete(AssistantConfirmation).where(AssistantConfirmation.thread_id.in_(thread_ids)))
    await db.execute(delete(AssistantMessage).where(AssistantMessage.thread_id.in_(thread_ids)))
    await db.execute(delete(AssistantThread).where(AssistantThread.owner_id == user.id))
    await db.execute(delete(Activity).where(Activity.athlete_id == user.id))
    await db.execute(delete(AthleteProfile).where(AthleteProfile.athlete_id == user.id))
    await db.execute(delete(Observation).where(Observation.athlete_id == user.id))
    await db.execute(delete(Checkin).where(Checkin.athlete_id == user.id))
    await db.execute(delete(Complaint).where(Complaint.athlete_id == user.id))
    await db.execute(delete(DailyLoad).where(DailyLoad.athlete_id == user.id))
    await db.execute(delete(Competition).where(Competition.athlete_id == user.id))
    await db.execute(delete(PrescribedWorkout).where(PrescribedWorkout.athlete_id == user.id))
    await db.execute(delete(TrainingBlock).where(TrainingBlock.athlete_id == user.id))
    await db.execute(delete(GroupMembership).where(GroupMembership.athlete_id == user.id))
    await db.execute(delete(PlanAssignment).where(PlanAssignment.athlete_id == user.id))
    await db.execute(delete(AthleteConnection).where(AthleteConnection.athlete_id == user.id))
    await db.execute(delete(Consent).where(Consent.user_id == user.id))
    await db.execute(
        update(CoachAthleteAssignment)
        .where((CoachAthleteAssignment.athlete_id == user.id) | (CoachAthleteAssignment.coach_id == user.id))
        .values(status="revoked", revoked_at=datetime.now(UTC))
    )
    await db.execute(
        update(OrganizationMembership).where(OrganizationMembership.user_id == user.id).values(status="revoked")
    )
    await db.execute(delete(UserRoleAssignment).where(UserRoleAssignment.user_id == user.id))
    user.email = f"deleted-{user.id}-{secrets.token_hex(6)}@invalid.local"
    user.first_name = "Cuenta"
    user.last_name = "eliminada"
    user.hashed_password = hash_password(secrets.token_urlsafe(48))
    user.deleted_at = utcnow()
    await db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/athletes/{athlete_id}/connections/intervals", response_model=ConnectionView)
async def connect_intervals(
    athlete_id: int,
    payload: ConnectionRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, user, athlete_id)
    if user.id != athlete_id and not user.is_superuser:
        raise HTTPException(403, "El atleta autoriza su propia conexión")
    if payload.mode == "real" and not (
        settings.INTERVALS_CLIENT_ID and settings.INTERVALS_CLIENT_SECRET and settings.PROVIDER_TOKEN_ENCRYPTION_KEY
    ):
        raise HTTPException(503, "INTERVALS_CONFIGURATION_REQUIRED")
    connection = await db.scalar(
        select(AthleteConnection).where(
            AthleteConnection.athlete_id == athlete_id,
            AthleteConnection.provider == "intervals_icu",
        )
    )
    if connection is None:
        connection = AthleteConnection(
            athlete_id=athlete_id,
            provider="intervals_icu",
            status="simulated" if payload.mode == "simulated" else "authorization_pending",
            scopes=[],
        )
        db.add(connection)
    else:
        connection.status = "simulated" if payload.mode == "simulated" else "authorization_pending"
    await db.commit()
    return connection


@router.get("/athletes/{athlete_id}/connections/intervals", response_model=ConnectionView)
async def get_intervals_connection(
    athlete_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, user, athlete_id)
    connection = await db.scalar(
        select(AthleteConnection).where(
            AthleteConnection.athlete_id == athlete_id,
            AthleteConnection.provider == "intervals_icu",
        )
    )
    if connection is None:
        return ConnectionView(provider="intervals_icu", status="not_connected", last_sync_at=None)
    return connection


@router.delete("/athletes/{athlete_id}/connections/intervals", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_intervals(
    athlete_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, user, athlete_id)
    if user.id != athlete_id and not user.is_superuser:
        raise HTTPException(403, "El atleta revoca su propia conexión")
    connection = await db.scalar(
        select(AthleteConnection).where(
            AthleteConnection.athlete_id == athlete_id,
            AthleteConnection.provider == "intervals_icu",
        )
    )
    if connection is None:
        raise HTTPException(404, "Conexión no encontrada")
    connection.status = "revoked"
    connection.access_token_enc = None
    connection.refresh_token_enc = None
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/admin/commercial/plans", status_code=status.HTTP_201_CREATED)
async def create_commercial_plan(
    payload: PlanCreate,
    admin: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_db),
):
    plan = CommercialPlan(**payload.model_dump())
    db.add(plan)
    await db.flush()
    add_audit(db, actor_id=admin.id, entity="commercial_plan", entity_id=plan.id, action="create")
    await db.commit()
    return {"id": plan.id, **payload.model_dump()}


@router.post("/admin/commercial/subscriptions", status_code=status.HTTP_201_CREATED)
async def create_subscription(
    payload: SubscriptionCreate,
    admin: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_db),
):
    if await db.get(CommercialPlan, payload.plan_id) is None:
        raise HTTPException(404, "Plan no encontrado")
    subscription = Subscription(status="active", **payload.model_dump())
    db.add(subscription)
    await db.flush()
    add_audit(db, actor_id=admin.id, entity="subscription", entity_id=subscription.id, action="activate")
    await db.commit()
    return {"id": subscription.id, "status": subscription.status, **payload.model_dump()}


@router.post("/admin/commercial/payments", status_code=status.HTTP_201_CREATED)
async def record_payment(
    payload: PaymentCreate,
    admin: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_db),
):
    if await db.get(Subscription, payload.subscription_id) is None:
        raise HTTPException(404, "Suscripción no encontrada")
    payment = ManagedPayment(recorded_by=admin.id, **payload.model_dump())
    db.add(payment)
    await db.flush()
    add_audit(db, actor_id=admin.id, entity="managed_payment", entity_id=payment.id, action="record")
    await db.commit()
    return {"id": payment.id, **payload.model_dump()}


@router.post("/recommendations", status_code=status.HTTP_201_CREATED)
async def create_recommendation(
    payload: RecommendationCreate,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, coach, payload.athlete_id)
    workout = await db.scalar(
        select(PrescribedWorkout).where(
            PrescribedWorkout.id == payload.workout_id,
            PrescribedWorkout.athlete_id == payload.athlete_id,
            PrescribedWorkout.coach_id == coach.id,
        )
    )
    if workout is None:
        raise HTTPException(404, "Sesión no encontrada")
    candidate_block_id = payload.changes.block_id or workout.block_id
    candidate_date = payload.changes.scheduled_date or workout.scheduled_date
    if candidate_block_id is not None:
        await check_block(candidate_block_id, payload.athlete_id, coach.id, candidate_date, db)
    recommendation = Recommendation(
        coach_id=coach.id,
        athlete_id=payload.athlete_id,
        workout_id=workout.id,
        base_plan_version=workout.version,
        evidence=payload.evidence,
        changes=payload.changes.model_dump(mode="json", exclude_none=True),
        rules_version="pilot-v1",
        model_version="simulated-v1",
    )
    db.add(recommendation)
    await db.commit()
    await db.refresh(recommendation)
    return {"id": recommendation.id, "status": recommendation.status}


@router.get("/recommendations", response_model=list[RecommendationView])
async def list_recommendations(
    athlete_id: int | None = Query(default=None, gt=0),
    recommendation_status: Literal["pending", "approved", "rejected"] | None = Query(default=None, alias="status"),
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    filters = [Recommendation.coach_id == coach.id]
    if athlete_id is not None:
        await require_athlete_access(db, coach, athlete_id)
        filters.append(Recommendation.athlete_id == athlete_id)
    if recommendation_status is not None:
        filters.append(Recommendation.status == recommendation_status)
    rows = await db.scalars(select(Recommendation).where(*filters).order_by(Recommendation.created_at.desc()))
    return [item for item in rows.all() if await has_athlete_access(db, coach, item.athlete_id)]


@router.post("/recommendations/{recommendation_id}/decision")
async def decide_recommendation(
    recommendation_id: int,
    payload: RecommendationDecision,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    recommendation = await db.scalar(
        select(Recommendation).where(
            Recommendation.id == recommendation_id,
            Recommendation.coach_id == coach.id,
            Recommendation.status == "pending",
        )
    )
    if recommendation is None:
        raise HTTPException(404, "Propuesta pendiente no encontrada")
    await require_athlete_access(db, coach, recommendation.athlete_id)
    if payload.action == "approve":
        changes = WorkoutChanges.model_validate(recommendation.changes).model_dump(exclude_none=True)
        changed = await db.execute(
            update(PrescribedWorkout)
            .where(
                PrescribedWorkout.id == recommendation.workout_id,
                PrescribedWorkout.athlete_id == recommendation.athlete_id,
                PrescribedWorkout.coach_id == coach.id,
                PrescribedWorkout.version == recommendation.base_plan_version,
                PrescribedWorkout.status == "draft",
            )
            .values(**changes, version=recommendation.base_plan_version + 1)
        )
        if changed.rowcount != 1:
            raise HTTPException(409, "La propuesta quedó obsoleta; vuelve a calcularla")
        recommendation.status = "approved"
    else:
        recommendation.status = "rejected"
    decision = Decision(
        recommendation_id=recommendation.id,
        actor_id=coach.id,
        action=payload.action,
        note=payload.note,
        decided_at=datetime.now(UTC),
    )
    db.add(decision)
    add_audit(
        db,
        actor_id=coach.id,
        entity="recommendation",
        entity_id=recommendation.id,
        action=payload.action,
    )
    await db.commit()
    return {"id": recommendation.id, "status": recommendation.status}
