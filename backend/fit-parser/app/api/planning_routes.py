from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import accessible_athlete, current_coach, current_user
from app.api.schemas import BlockCreate, BlockView, PublishWorkout, WorkoutCreate, WorkoutReplace, WorkoutView
from app.core.database import get_db
from app.infrastructure.database.models import PrescribedWorkout, TrainingBlock, User

router = APIRouter(prefix="/athletes/{athlete_id}", tags=["Planning"])


def serialize_steps(value):
    return [group.model_dump(mode="json") for group in value]


def block_view(block: TrainingBlock) -> BlockView:
    return BlockView.model_validate(block)


def workout_view(workout: PrescribedWorkout) -> WorkoutView:
    return WorkoutView(
        id=workout.id, athlete_id=workout.athlete_id, coach_id=workout.coach_id, title=workout.title,
        description=workout.description, scheduled_date=workout.scheduled_date, sport_type=workout.sport_type,
        block_id=workout.block_id, steps=workout.steps, status=workout.status, version=workout.version,
    )


async def require_coached_athlete(athlete_id: int, coach: User, db: AsyncSession) -> User:
    return await accessible_athlete(db, coach, athlete_id)


@router.post("/blocks", response_model=BlockView, status_code=status.HTTP_201_CREATED)
async def create_block(
    athlete_id: int, payload: BlockCreate, coach: User = Depends(current_coach), db: AsyncSession = Depends(get_db),
):
    await require_coached_athlete(athlete_id, coach, db)
    block = TrainingBlock(athlete_id=athlete_id, coach_id=coach.id, **payload.model_dump())
    db.add(block)
    await db.commit()
    await db.refresh(block)
    return block_view(block)


@router.get("/blocks", response_model=list[BlockView])
async def list_blocks(
    athlete_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    await accessible_athlete(db, user, athlete_id)
    result = await db.scalars(select(TrainingBlock).where(TrainingBlock.athlete_id == athlete_id))
    return [block_view(item) for item in result]


async def check_block(block_id: int | None, athlete_id: int, coach_id: int, db: AsyncSession):
    if block_id is None:
        return
    block = await db.scalar(select(TrainingBlock).where(
        TrainingBlock.id == block_id, TrainingBlock.athlete_id == athlete_id, TrainingBlock.coach_id == coach_id,
    ))
    if block is None:
        raise HTTPException(422, "El bloque no pertenece a este atleta")


@router.post("/workouts", response_model=WorkoutView, status_code=status.HTTP_201_CREATED)
async def create_workout(
    athlete_id: int, payload: WorkoutCreate, coach: User = Depends(current_coach), db: AsyncSession = Depends(get_db),
):
    await require_coached_athlete(athlete_id, coach, db)
    await check_block(payload.block_id, athlete_id, coach.id, db)
    workout = PrescribedWorkout(
        athlete_id=athlete_id, coach_id=coach.id, title=payload.title, description=payload.description,
        scheduled_date=payload.scheduled_date, sport_type=payload.sport_type, block_id=payload.block_id,
        steps=serialize_steps(payload.steps),
    )
    db.add(workout)
    await db.commit()
    await db.refresh(workout)
    return workout_view(workout)


@router.get("/workouts", response_model=list[WorkoutView])
async def list_workouts(
    athlete_id: int, start: date, end: date, user: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    if end < start:
        raise HTTPException(422, "El fin debe ser igual o posterior al inicio")
    await accessible_athlete(db, user, athlete_id)
    start_at, end_at = datetime.combine(start, time.min), datetime.combine(end, time.max)
    result = await db.scalars(select(PrescribedWorkout).where(
        PrescribedWorkout.athlete_id == athlete_id,
        PrescribedWorkout.scheduled_date.between(start_at, end_at),
    ).order_by(PrescribedWorkout.scheduled_date))
    return [workout_view(item) for item in result]


@router.put("/workouts/{workout_id}", response_model=WorkoutView)
async def replace_workout(
    athlete_id: int, workout_id: int, payload: WorkoutReplace, coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    await require_coached_athlete(athlete_id, coach, db)
    workout = await db.scalar(select(PrescribedWorkout).where(
        PrescribedWorkout.id == workout_id, PrescribedWorkout.athlete_id == athlete_id, PrescribedWorkout.coach_id == coach.id,
    ))
    if workout is None:
        raise HTTPException(404, "Sesión no encontrada")
    if workout.version != payload.expected_version:
        raise HTTPException(409, "La sesión cambió; actualiza antes de guardar")
    if workout.status != "draft":
        raise HTTPException(409, "Solo se editan borradores en esta versión")
    await check_block(payload.block_id, athlete_id, coach.id, db)
    for field in ("title", "description", "scheduled_date", "sport_type", "block_id"):
        setattr(workout, field, getattr(payload, field))
    workout.steps = serialize_steps(payload.steps)
    workout.version += 1
    await db.commit()
    await db.refresh(workout)
    return workout_view(workout)


@router.post("/workouts/{workout_id}/publish", response_model=WorkoutView)
async def publish_workout(
    athlete_id: int, workout_id: int, payload: PublishWorkout, coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    await require_coached_athlete(athlete_id, coach, db)
    workout = await db.scalar(select(PrescribedWorkout).where(
        PrescribedWorkout.id == workout_id, PrescribedWorkout.athlete_id == athlete_id, PrescribedWorkout.coach_id == coach.id,
    ))
    if workout is None:
        raise HTTPException(404, "Sesión no encontrada")
    if workout.version != payload.expected_version:
        raise HTTPException(409, "La sesión cambió; actualiza antes de publicar")
    workout.status = "published"
    workout.version += 1
    await db.commit()
    await db.refresh(workout)
    return workout_view(workout)
