from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import accessible_athlete, current_coach, current_user
from app.api.schemas import BlockCreate, BlockView, PublishWorkout, WorkoutCreate, WorkoutReplace, WorkoutView
from app.core.database import get_db
from app.infrastructure.database.models import PrescribedWorkout, TrainingBlock, User
from app.services.access import roles_for
from app.services.audit import add_audit

router = APIRouter(prefix="/athletes/{athlete_id}", tags=["Planning"])


def serialize_steps(value):
    return [group.model_dump(mode="json") for group in value]


def block_view(block: TrainingBlock) -> BlockView:
    return BlockView.model_validate(block)


def workout_view(workout: PrescribedWorkout) -> WorkoutView:
    return WorkoutView(
        id=workout.id,
        athlete_id=workout.athlete_id,
        coach_id=workout.coach_id,
        title=workout.title,
        description=workout.description,
        scheduled_date=workout.scheduled_date,
        sport_type=workout.sport_type,
        block_id=workout.block_id,
        steps=workout.steps,
        status=workout.status,
        version=workout.version,
    )


async def require_coached_athlete(athlete_id: int, coach: User, db: AsyncSession) -> User:
    return await accessible_athlete(db, coach, athlete_id)


@router.post("/blocks", response_model=BlockView, status_code=status.HTTP_201_CREATED)
async def create_block(
    athlete_id: int,
    payload: BlockCreate,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    await require_coached_athlete(athlete_id, coach, db)
    block = TrainingBlock(athlete_id=athlete_id, coach_id=coach.id, **payload.model_dump())
    db.add(block)
    await db.flush()
    add_audit(
        db,
        actor_id=coach.id,
        entity="training_block",
        entity_id=block.id,
        action="create",
        after=payload.model_dump(mode="json"),
    )
    await db.commit()
    await db.refresh(block)
    return block_view(block)


@router.get("/blocks", response_model=list[BlockView])
async def list_blocks(
    athlete_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await accessible_athlete(db, user, athlete_id)
    result = await db.scalars(select(TrainingBlock).where(TrainingBlock.athlete_id == athlete_id))
    return [block_view(item) for item in result]


async def check_block(block_id: int | None, athlete_id: int, coach_id: int, scheduled_date: datetime, db: AsyncSession):
    if block_id is None:
        return
    block = await db.scalar(
        select(TrainingBlock).where(
            TrainingBlock.id == block_id,
            TrainingBlock.athlete_id == athlete_id,
            TrainingBlock.coach_id == coach_id,
        )
    )
    if block is None:
        raise HTTPException(422, "El bloque no pertenece a este atleta")
    if not block.start_date <= scheduled_date.date() <= block.end_date:
        raise HTTPException(422, "La sesión debe quedar dentro de las fechas del bloque")


@router.post("/workouts", response_model=WorkoutView, status_code=status.HTTP_201_CREATED)
async def create_workout(
    athlete_id: int,
    payload: WorkoutCreate,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    await require_coached_athlete(athlete_id, coach, db)
    await check_block(payload.block_id, athlete_id, coach.id, payload.scheduled_date, db)
    workout = PrescribedWorkout(
        athlete_id=athlete_id,
        coach_id=coach.id,
        title=payload.title,
        description=payload.description,
        scheduled_date=payload.scheduled_date,
        sport_type=payload.sport_type,
        block_id=payload.block_id,
        steps=serialize_steps(payload.steps),
    )
    db.add(workout)
    await db.commit()
    await db.refresh(workout)
    return workout_view(workout)


@router.get("/workouts", response_model=list[WorkoutView])
async def list_workouts(
    athlete_id: int,
    start: date,
    end: date,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if end < start:
        raise HTTPException(422, "El fin debe ser igual o posterior al inicio")
    await accessible_athlete(db, user, athlete_id)
    start_at, end_at = datetime.combine(start, time.min), datetime.combine(end, time.max)
    result = await db.scalars(
        select(PrescribedWorkout)
        .where(
            PrescribedWorkout.athlete_id == athlete_id,
            PrescribedWorkout.scheduled_date.between(start_at, end_at),
            *(
                []
                if "coach" in await roles_for(db, user.id) or user.is_superuser
                else [PrescribedWorkout.status == "published"]
            ),
        )
        .order_by(PrescribedWorkout.scheduled_date)
    )
    return [workout_view(item) for item in result]


@router.put("/workouts/{workout_id}", response_model=WorkoutView)
async def replace_workout(
    athlete_id: int,
    workout_id: int,
    payload: WorkoutReplace,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    await require_coached_athlete(athlete_id, coach, db)
    await check_block(payload.block_id, athlete_id, coach.id, payload.scheduled_date, db)
    workout = await db.scalar(
        update(PrescribedWorkout)
        .where(
            PrescribedWorkout.id == workout_id,
            PrescribedWorkout.athlete_id == athlete_id,
            PrescribedWorkout.coach_id == coach.id,
            PrescribedWorkout.version == payload.expected_version,
            PrescribedWorkout.status == "draft",
        )
        .values(
            title=payload.title,
            description=payload.description,
            scheduled_date=payload.scheduled_date,
            sport_type=payload.sport_type,
            block_id=payload.block_id,
            steps=serialize_steps(payload.steps),
            version=payload.expected_version + 1,
        )
        .returning(PrescribedWorkout)
    )
    if workout is None:
        existing = await db.scalar(
            select(PrescribedWorkout).where(
                PrescribedWorkout.id == workout_id,
                PrescribedWorkout.athlete_id == athlete_id,
                PrescribedWorkout.coach_id == coach.id,
            )
        )
        if existing is None:
            raise HTTPException(404, "Sesión no encontrada")
        raise HTTPException(409, "La sesión cambió o ya fue publicada; actualiza antes de guardar")
    add_audit(
        db,
        actor_id=coach.id,
        entity="prescribed_workout",
        entity_id=workout_id,
        action="replace_draft",
        after={"version": workout.version},
    )
    await db.commit()
    return workout_view(workout)


@router.post("/workouts/{workout_id}/publish", response_model=WorkoutView)
async def publish_workout(
    athlete_id: int,
    workout_id: int,
    payload: PublishWorkout,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    await require_coached_athlete(athlete_id, coach, db)
    workout = await db.scalar(
        select(PrescribedWorkout).where(
            PrescribedWorkout.id == workout_id,
            PrescribedWorkout.athlete_id == athlete_id,
            PrescribedWorkout.coach_id == coach.id,
        )
    )
    if workout is None:
        raise HTTPException(404, "Sesión no encontrada")
    if workout.status == "published":
        return workout_view(workout)
    if workout.version != payload.expected_version:
        raise HTTPException(409, "La sesión cambió; actualiza antes de publicar")
    published = await db.scalar(
        update(PrescribedWorkout)
        .where(
            PrescribedWorkout.id == workout_id,
            PrescribedWorkout.version == payload.expected_version,
            PrescribedWorkout.status == "draft",
        )
        .values(status="published", version=payload.expected_version + 1)
        .returning(PrescribedWorkout)
    )
    if published is None:
        current = await db.get(PrescribedWorkout, workout_id)
        if current is not None and current.status == "published":
            return workout_view(current)
        raise HTTPException(409, "La sesión cambió; actualiza antes de publicar")
    add_audit(
        db,
        actor_id=coach.id,
        entity="prescribed_workout",
        entity_id=workout_id,
        action="publish",
        after={"version": published.version},
    )
    await db.commit()
    return workout_view(published)
