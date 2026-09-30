from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy import case, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_coach, current_user
from app.api.insight_routes import router as insight_router
from app.api.planning_routes import check_block, workout_view
from app.api.product_schemas import (
    CheckinUpsert,
    CheckinView,
    CompetitionCreate,
    CompetitionReplace,
    CompetitionView,
    ComplaintCreate,
    ComplaintUpdateCreate,
    ComplaintView,
    ConnectionRequest,
    ConnectionView,
    GroupCreate,
    GroupMemberCreate,
    GroupMemberView,
    GroupView,
    MemberReplace,
    ObservationCreate,
    ObservationView,
    ProfileUpsert,
    ProfileView,
    RecommendationCreate,
    RecommendationDecision,
    RecommendationView,
    ReviewDecision,
    ReviewItemView,
    TemplateApply,
    TemplateCreate,
    TemplateReplace,
    TemplateView,
)
from app.api.schemas import WorkoutCreate
from app.core.database import get_db
from app.domain.comparison import local_day
from app.infrastructure.database.models import PrescribedWorkout, User
from app.infrastructure.database.models.product import (
    AthleteConnection,
    AthleteGroup,
    AthleteProfile,
    AuditLog,
    Checkin,
    CoachAthleteAssignment,
    Competition,
    Complaint,
    ComplaintUpdate,
    Decision,
    GroupMembership,
    Observation,
    PlanAssignment,
    PlanTemplate,
    Recommendation,
    ReviewItem,
)
from app.services.access import has_athlete_access, primary_organization_id, require_athlete_access
from app.services.audit import add_audit
from app.services.product_notifications import notify_assigned_coaches, queue_product_event

router = APIRouter(tags=["Pilot product"])
router.include_router(insight_router)


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
    await db.scalar(select(User).where(User.id == athlete_id).with_for_update())
    current = await db.scalar(
        select(AthleteProfile).where(
            AthleteProfile.athlete_id == athlete_id,
            AthleteProfile.valid_to.is_(None),
        )
    )
    if current is not None:
        if payload.valid_from <= current.valid_from:
            raise HTTPException(409, "La nueva vigencia debe iniciar después del perfil actual")
        current.valid_to = payload.valid_from - timedelta(days=1)
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
    athlete = await db.get(User, athlete_id)
    profile = await db.scalar(
        select(AthleteProfile)
        .where(
            AthleteProfile.athlete_id == athlete_id,
            AthleteProfile.valid_from <= date.fromisoformat(local_day(datetime.now(UTC), athlete.timezone)),
            (
                AthleteProfile.valid_to.is_(None)
                | (AthleteProfile.valid_to >= date.fromisoformat(local_day(datetime.now(UTC), athlete.timezone)))
            ),
        )
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
        item.version += 1
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
    await notify_assigned_coaches(
        db,
        athlete_id=athlete_id,
        category="review",
        event_key=f"complaint:{complaint.id}:{complaint.version}",
        entity="complaint",
        entity_id=complaint.id,
        entity_version=complaint.version,
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
    complaint = await db.scalar(select(Complaint).where(Complaint.id == complaint_id).with_for_update())
    if complaint is None:
        raise HTTPException(404, "Molestia no encontrada")
    await require_athlete_access(db, user, complaint.athlete_id)
    if user.id != complaint.athlete_id and not user.is_superuser:
        raise HTTPException(403, "Sólo el atleta actualiza su molestia")
    if payload.expected_version is not None and payload.expected_version != complaint.version:
        raise HTTPException(409, "La molestia cambió; recarga su evolución")
    before = {"intensity_0_10": complaint.intensity_0_10, "status": complaint.status}
    complaint.version += 1
    worsened = payload.intensity_0_10 > complaint.intensity_0_10 or (
        payload.limits_movement and not complaint.limits_movement
    )
    db.add(
        ComplaintUpdate(complaint_id=complaint.id, actor_id=user.id, **payload.model_dump(exclude={"expected_version"}))
    )
    complaint.intensity_0_10 = payload.intensity_0_10
    complaint.limits_movement = payload.limits_movement
    complaint.note = payload.note
    if worsened or complaint.status == "closed":
        complaint.status = "reported"
        await open_complaint_review(
            db,
            complaint,
            "high" if worsened or payload.limits_movement or payload.intensity_0_10 >= 7 else "normal",
            "La molestia empeoró o se reabrió",
        )
        await notify_assigned_coaches(
            db,
            athlete_id=complaint.athlete_id,
            category="review",
            event_key=f"complaint:{complaint.id}:{complaint.version}",
            entity="complaint",
            entity_id=complaint.id,
            entity_version=complaint.version,
        )
    add_audit(
        db,
        actor_id=user.id,
        entity="complaint",
        entity_id=complaint.id,
        action="update",
        before=before,
        after={"intensity_0_10": complaint.intensity_0_10, "status": complaint.status},
    )
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
        .order_by(case((ReviewItem.priority == "high", 0), else_=1), ReviewItem.created_at, ReviewItem.id)
    )
    return [item for item in rows.all() if await has_athlete_access(db, coach, item.athlete_id)]


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
    complaint = await db.scalar(select(Complaint).where(Complaint.id == item.complaint_id).with_for_update())
    expected = payload.expected_version if payload.expected_version is not None else item.version
    changed = await db.execute(
        update(ReviewItem)
        .where(ReviewItem.id == item.id, ReviewItem.version == expected)
        .values(status=payload.status, decided_by=coach.id, decision_note=payload.note, version=expected + 1)
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "El caso cambió; recarga antes de decidir")
    if complaint is not None:
        complaint.status = payload.status
        complaint.version += 1
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
    await db.flush()
    add_audit(db, actor_id=coach.id, entity="athlete_group", entity_id=group.id, action="create")
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
    return {"id": member.id, "group_id": group_id, "version": member.version, **payload.model_dump()}


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
    return [item for item in rows.all() if await has_athlete_access(db, coach, item.athlete_id)]


@router.post("/templates", response_model=TemplateView, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: TemplateCreate,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    validate_template(payload.workouts, payload.sport_type)
    template = PlanTemplate(
        organization_id=await primary_organization_id(db, coach.id),
        coach_id=coach.id,
        **payload.model_dump(),
    )
    db.add(template)
    await db.flush()
    add_audit(db, actor_id=coach.id, entity="plan_template", entity_id=template.id, action="create")
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


def parse_workout(raw: dict, sport: str) -> WorkoutCreate:
    candidate = {key: value for key, value in raw.items() if key != "key"}
    try:
        return WorkoutCreate.model_validate({**candidate, "sport_type": candidate.get("sport_type", sport)})
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_context=False)) from None


def validate_template(workouts: list[dict], sport: str) -> None:
    keys = [str(item.get("key", index)) for index, item in enumerate(workouts)]
    if len(set(keys)) != len(keys):
        raise HTTPException(422, "Las claves de sesión deben ser únicas")
    for item in workouts:
        parse_workout(item, sport)


@router.put("/templates/{template_id}", response_model=TemplateView)
async def replace_template(
    template_id: int, payload: TemplateReplace, coach: User = Depends(current_coach), db: AsyncSession = Depends(get_db)
):
    validate_template(payload.workouts, payload.sport_type)
    template = await db.scalar(
        update(PlanTemplate)
        .where(
            PlanTemplate.id == template_id,
            PlanTemplate.coach_id == coach.id,
            PlanTemplate.version == payload.expected_version,
        )
        .values(**payload.model_dump(exclude={"expected_version"}), version=payload.expected_version + 1)
        .returning(PlanTemplate)
    )
    if template is None:
        raise HTTPException(409, "La plantilla cambió o ya no está disponible")
    add_audit(
        db,
        actor_id=coach.id,
        entity="plan_template",
        entity_id=template.id,
        action="replace",
        after={"version": template.version},
    )
    await db.commit()
    return template


@router.get("/templates/{template_id}/assignments")
async def template_assignments(
    template_id: int, coach: User = Depends(current_coach), db: AsyncSession = Depends(get_db)
):
    template = await db.scalar(
        select(PlanTemplate).where(PlanTemplate.id == template_id, PlanTemplate.coach_id == coach.id)
    )
    if template is None:
        raise HTTPException(404, "Plantilla no encontrada")
    rows = await db.scalars(select(PlanAssignment).where(PlanAssignment.template_id == template_id))
    return [
        {
            "athlete_id": row.athlete_id,
            "overrides": row.overrides,
            "applied_version": row.applied_version,
            "workout_refs": row.workout_refs,
        }
        for row in rows.all()
        if await has_athlete_access(db, coach, row.athlete_id)
    ]


@router.post("/templates/{template_id}/apply")
async def apply_template(
    template_id: int, payload: TemplateApply, coach: User = Depends(current_coach), db: AsyncSession = Depends(get_db)
):
    template = await db.scalar(
        select(PlanTemplate).where(PlanTemplate.id == template_id, PlanTemplate.coach_id == coach.id).with_for_update()
    )
    if template is None:
        raise HTTPException(404, "Plantilla no encontrada")
    if payload.expected_version is not None and payload.expected_version != template.version:
        raise HTTPException(409, "La plantilla cambió; recarga antes de aplicar")
    members = {}
    if payload.group_id is not None:
        group = await db.scalar(
            select(AthleteGroup).where(AthleteGroup.id == payload.group_id, AthleteGroup.coach_id == coach.id)
        )
        if group is None:
            raise HTTPException(404, "Grupo no encontrado")
        rows = await db.scalars(select(GroupMembership).where(GroupMembership.group_id == group.id))
        members = {item.athlete_id: item.overrides for item in rows.all()}
    athlete_ids = sorted(set(payload.athlete_ids) | set(members))
    if not athlete_ids or len(athlete_ids) > 100:
        raise HTTPException(422, "Selecciona entre 1 y 100 atletas")
    changed_ids, skipped = [], []
    for athlete_id in athlete_ids:
        await require_athlete_access(db, coach, athlete_id)
        athlete = await db.scalar(select(User).where(User.id == athlete_id).with_for_update())
        assignment = await db.scalar(
            select(PlanAssignment).where(
                PlanAssignment.template_id == template.id, PlanAssignment.athlete_id == athlete_id
            )
        )
        old_overrides = assignment.overrides if assignment is not None else {}
        individual_overrides = {**old_overrides, **payload.overrides.get(athlete_id, {})}
        overrides = {**members.get(athlete_id, {}), **individual_overrides}
        if assignment is not None and not assignment.workout_refs:
            raise HTTPException(409, "Asignación anterior sin trazabilidad: revisa sus sesiones antes de reaplicar")
        if assignment is None:
            assignment = PlanAssignment(
                template_id=template.id,
                athlete_id=athlete_id,
                overrides=overrides,
                applied_version=template.version,
                workout_refs={},
            )
            db.add(assignment)
        refs = dict(assignment.workout_refs)
        keys = {str(raw.get("key", index)) for index, raw in enumerate(template.workouts)}
        if set(refs) - keys:
            raise HTTPException(
                409, "La plantilla elimina sesiones asignadas; conserva sus claves y revisa cada borrador"
            )
        profile = await db.scalar(
            select(AthleteProfile)
            .where(
                AthleteProfile.athlete_id == athlete_id,
                AthleteProfile.valid_from <= date.fromisoformat(local_day(datetime.now(UTC), athlete.timezone)),
            )
            .order_by(AthleteProfile.valid_from.desc())
            .limit(1)
        )
        weekdays = overrides.get(
            "available_weekdays",
            (profile.availability or {}).get("available_weekdays") if profile is not None else None,
        )
        if weekdays is not None and (
            not isinstance(weekdays, list) or any(type(day) is not int or day not in range(7) for day in weekdays)
        ):
            raise HTTPException(422, "Disponibilidad: usa días de 0 (lunes) a 6 (domingo)")
        for index, raw in enumerate(template.workouts):
            key = str(raw.get("key", index))
            exception = overrides.get(key, {})
            if not isinstance(exception, dict):
                raise HTTPException(422, "La excepción de una sesión debe ser un objeto")
            parsed = parse_workout({**raw, **exception}, template.sport_type)
            day = date.fromisoformat(local_day(parsed.scheduled_date, athlete.timezone))
            if weekdays is not None and day.weekday() not in weekdays:
                skipped.append({"athlete_id": athlete_id, "key": key, "reason": "unavailable_day"})
                continue
            await check_block(parsed.block_id, athlete_id, coach.id, parsed.scheduled_date, db)
            values = parsed.model_dump(exclude={"steps"}) | {"steps": serialize_steps(parsed.steps)}
            ref = refs.get(key)
            if ref is None:
                workout = PrescribedWorkout(athlete_id=athlete_id, coach_id=coach.id, **values)
                db.add(workout)
                await db.flush()
            else:
                workout = await db.scalar(
                    select(PrescribedWorkout)
                    .where(
                        PrescribedWorkout.id == ref["id"],
                        PrescribedWorkout.athlete_id == athlete_id,
                        PrescribedWorkout.coach_id == coach.id,
                    )
                    .with_for_update()
                )
                if workout is None or workout.status != "draft" or workout.version != ref["version"]:
                    skipped.append({"athlete_id": athlete_id, "key": key, "reason": "published_or_individually_edited"})
                    continue
                old_values = {field: getattr(workout, field) for field in values}
                old_values["scheduled_date"] = (
                    workout.scheduled_date.replace(tzinfo=UTC)
                    if workout.scheduled_date.tzinfo is None
                    else workout.scheduled_date
                )
                if old_values == values:
                    continue
                for field, value in values.items():
                    setattr(workout, field, value)
                workout.version += 1
            refs[key] = {"id": workout.id, "version": workout.version}
            changed_ids.append(workout.id)
            add_audit(
                db,
                actor_id=coach.id,
                entity="prescribed_workout",
                entity_id=workout.id,
                action="apply_template",
                after={"template_id": template.id, "template_version": template.version, "version": workout.version},
            )
        assignment.workout_refs, assignment.overrides, assignment.applied_version = (
            refs,
            individual_overrides,
            template.version,
        )
    await db.commit()
    return {"template_id": template.id, "version": template.version, "workout_ids": changed_ids, "skipped": skipped}


@router.get("/athletes/{athlete_id}/profile/history", response_model=list[ProfileView])
async def profile_history(athlete_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await require_athlete_access(db, user, athlete_id)
    return (
        await db.scalars(
            select(AthleteProfile)
            .where(AthleteProfile.athlete_id == athlete_id)
            .order_by(AthleteProfile.valid_from.desc())
        )
    ).all()


@router.get("/athletes/{athlete_id}/checkins", response_model=list[CheckinView])
async def checkin_history(
    athlete_id: int, start: date, end: date, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await require_athlete_access(db, user, athlete_id)
    if end < start or (end - start).days > 366:
        raise HTTPException(422, "Selecciona hasta un año de sensaciones")
    return (
        await db.scalars(
            select(Checkin)
            .where(Checkin.athlete_id == athlete_id, Checkin.local_date.between(start, end))
            .order_by(Checkin.local_date.desc())
        )
    ).all()


@router.get("/complaints/{complaint_id}")
async def complaint_history(complaint_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    complaint = await db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(404, "Molestia no encontrada")
    await require_athlete_access(db, user, complaint.athlete_id)
    updates = (
        await db.scalars(
            select(ComplaintUpdate)
            .where(ComplaintUpdate.complaint_id == complaint.id)
            .order_by(ComplaintUpdate.created_at, ComplaintUpdate.id)
        )
    ).all()
    review = await db.scalar(select(ReviewItem).where(ReviewItem.complaint_id == complaint.id))
    decisions = (
        []
        if review is None
        else (
            await db.scalars(
                select(AuditLog)
                .where(AuditLog.entity == "review_item", AuditLog.entity_id == str(review.id))
                .order_by(AuditLog.at, AuditLog.id)
            )
        ).all()
    )
    return {
        "complaint": ComplaintView.model_validate(complaint),
        "updates": [
            {
                "id": item.id,
                "intensity_0_10": item.intensity_0_10,
                "limits_movement": item.limits_movement,
                "note": item.note,
                "created_at": item.created_at,
            }
            for item in updates
        ],
        "review": ReviewItemView.model_validate(review) if review is not None else None,
        "decisions": [
            {"action": item.action, "at": item.at, "note": (item.after or {}).get("note")} for item in decisions
        ],
    }


@router.put("/athletes/{athlete_id}/competitions/{competition_id}", response_model=CompetitionView)
async def replace_competition(
    athlete_id: int,
    competition_id: int,
    payload: CompetitionReplace,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, coach, athlete_id)
    row = await db.scalar(
        update(Competition)
        .where(
            Competition.id == competition_id,
            Competition.athlete_id == athlete_id,
            Competition.coach_id == coach.id,
            Competition.version == payload.expected_version,
        )
        .values(**payload.model_dump(exclude={"expected_version"}), version=payload.expected_version + 1)
        .returning(Competition)
    )
    if row is None:
        raise HTTPException(409, "La competencia cambió o ya no está disponible")
    add_audit(
        db, actor_id=coach.id, entity="competition", entity_id=row.id, action="replace", after={"version": row.version}
    )
    await db.commit()
    return row


@router.delete("/athletes/{athlete_id}/competitions/{competition_id}", status_code=204)
async def remove_competition(
    athlete_id: int,
    competition_id: int,
    expected_version: int = Query(ge=1),
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, coach, athlete_id)
    changed = await db.execute(
        delete(Competition).where(
            Competition.id == competition_id,
            Competition.athlete_id == athlete_id,
            Competition.coach_id == coach.id,
            Competition.version == expected_version,
        )
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "La competencia cambió o ya no está disponible")
    add_audit(db, actor_id=coach.id, entity="competition", entity_id=competition_id, action="remove")
    await db.commit()
    return Response(status_code=204)


async def owned_member(db, coach, group_id, athlete_id):
    group = await db.scalar(select(AthleteGroup).where(AthleteGroup.id == group_id, AthleteGroup.coach_id == coach.id))
    if group is None:
        raise HTTPException(404, "Grupo no encontrado")
    await require_athlete_access(db, coach, athlete_id)


@router.put("/groups/{group_id}/members/{athlete_id}", response_model=GroupMemberView)
async def replace_member(
    group_id: int,
    athlete_id: int,
    payload: MemberReplace,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    await owned_member(db, coach, group_id, athlete_id)
    row = await db.scalar(
        update(GroupMembership)
        .where(
            GroupMembership.group_id == group_id,
            GroupMembership.athlete_id == athlete_id,
            GroupMembership.version == payload.expected_version,
        )
        .values(overrides=payload.overrides, version=payload.expected_version + 1)
        .returning(GroupMembership)
    )
    if row is None:
        raise HTTPException(409, "La excepción cambió; recarga el grupo")
    add_audit(
        db,
        actor_id=coach.id,
        entity="group_membership",
        entity_id=row.id,
        action="replace_exception",
        after={"version": row.version},
    )
    await db.commit()
    return row


@router.delete("/groups/{group_id}/members/{athlete_id}", status_code=204)
async def remove_member(
    group_id: int,
    athlete_id: int,
    expected_version: int = Query(ge=1),
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    await owned_member(db, coach, group_id, athlete_id)
    changed = await db.execute(
        delete(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.athlete_id == athlete_id,
            GroupMembership.version == expected_version,
        )
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "El miembro cambió; recarga el grupo")
    await db.commit()
    return Response(status_code=204)


@router.post("/athletes/{athlete_id}/connections/intervals", response_model=ConnectionView)
async def connect_intervals(
    athlete_id: int,
    payload: ConnectionRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, user, athlete_id)
    raise HTTPException(410, "Usa /connections/intervals/{athlete_id}/authorize")


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
    raise HTTPException(410, "Usa DELETE /connections/intervals/{athlete_id}")


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
    if workout.status != "draft":
        raise HTTPException(409, "Las propuestas requieren una sesión en borrador")
    candidate_workout(workout, payload.changes.model_dump(mode="json", exclude_none=True))
    candidate_block_id = payload.changes.block_id or workout.block_id
    candidate_date = payload.changes.scheduled_date or workout.scheduled_date
    if candidate_block_id is not None:
        await check_block(candidate_block_id, payload.athlete_id, coach.id, candidate_date, db)
    recommendation = Recommendation(
        coach_id=coach.id,
        athlete_id=payload.athlete_id,
        workout_id=workout.id,
        base_plan_version=workout.version,
        evidence=[
            *payload.evidence,
            {"source": "plan_snapshot", "snapshot": workout_view(workout).model_dump(mode="json")},
        ],
        changes=payload.changes.model_dump(mode="json", exclude_none=True),
        rules_version="pilot-v1",
        model_version="simulated-v1",
    )
    db.add(recommendation)
    await db.flush()
    await queue_product_event(
        db,
        recipient_id=coach.id,
        athlete_id=payload.athlete_id,
        category="review",
        event_key=f"proposal:{recommendation.id}:pending",
        entity="recommendation",
        entity_id=recommendation.id,
    )
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


def candidate_workout(workout, changes: dict) -> WorkoutCreate:
    scheduled = workout.scheduled_date
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=UTC)
    raw = {
        "title": workout.title,
        "description": workout.description,
        "scheduled_date": scheduled,
        "sport_type": workout.sport_type,
        "block_id": workout.block_id,
        "steps": workout.steps,
    }
    return parse_workout({**raw, **changes}, workout.sport_type)


@router.post("/recommendations/{recommendation_id}/decision")
async def decide_recommendation(
    recommendation_id: int,
    payload: RecommendationDecision,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    recommendation = await db.scalar(
        select(Recommendation)
        .where(Recommendation.id == recommendation_id, Recommendation.coach_id == coach.id)
        .with_for_update()
    )
    if recommendation is None:
        raise HTTPException(404, "Propuesta no encontrada")
    await require_athlete_access(db, coach, recommendation.athlete_id)
    if recommendation.status != "pending":
        raise HTTPException(409, "La propuesta ya tiene una decisión")
    workout = await db.scalar(
        select(PrescribedWorkout)
        .where(
            PrescribedWorkout.id == recommendation.workout_id,
            PrescribedWorkout.athlete_id == recommendation.athlete_id,
            PrescribedWorkout.coach_id == coach.id,
        )
        .with_for_update()
    )
    if payload.action in {"approve", "modify"}:
        expected = payload.expected_plan_version or recommendation.base_plan_version
        if expected != recommendation.base_plan_version or workout is None:
            raise HTTPException(409, "La propuesta quedó obsoleta; vuelve a calcularla")
        if payload.action == "modify" and payload.changes is None:
            raise HTTPException(422, "Indica los cambios de la propuesta")
        if payload.action == "approve" and payload.changes is not None:
            raise HTTPException(422, "Usa modificar para cambiar la propuesta")
        changes = recommendation.changes | (
            payload.changes.model_dump(mode="json", exclude_none=True) if payload.changes else {}
        )
        parsed = candidate_workout(workout, changes)
        await check_block(parsed.block_id, recommendation.athlete_id, coach.id, parsed.scheduled_date, db)
        changed = await db.execute(
            update(PrescribedWorkout)
            .where(
                PrescribedWorkout.id == workout.id,
                PrescribedWorkout.version == expected,
                PrescribedWorkout.status == "draft",
            )
            .values(**parsed.model_dump(exclude={"steps"}), steps=serialize_steps(parsed.steps), version=expected + 1)
        )
        if changed.rowcount != 1:
            raise HTTPException(409, "La propuesta quedó obsoleta; vuelve a calcularla")
        recommendation.changes = changes
        recommendation.status = "approved"
    else:
        if payload.changes is not None:
            raise HTTPException(422, "Rechazar no admite cambios de sesión")
        recommendation.status = "rejected"
    db.add(
        Decision(
            recommendation_id=recommendation.id,
            actor_id=coach.id,
            action=payload.action,
            note=payload.note,
            decided_at=datetime.now(UTC),
        )
    )
    add_audit(
        db,
        actor_id=coach.id,
        entity="recommendation",
        entity_id=recommendation.id,
        action=payload.action,
        before={"base_plan_version": recommendation.base_plan_version},
        after={"note": payload.note, "changes": recommendation.changes, "status": recommendation.status},
    )
    await db.commit()
    if workout is not None:
        await db.refresh(workout)
    return {
        "id": recommendation.id,
        "status": recommendation.status,
        "workout": workout_view(workout) if workout is not None else None,
    }
