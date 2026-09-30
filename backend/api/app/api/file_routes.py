from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_user
from app.core.database import get_db
from app.infrastructure.database.models import Activity, User
from app.services.access import require_athlete_access
from app.services.object_store import ObjectStoreError, read_file

router = APIRouter(tags=["Private files"])


@router.get("/athletes/{athlete_id}/activities/{activity_id}/file")
async def activity_file(
    athlete_id: int, activity_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await require_athlete_access(db, user, athlete_id)
    activity = await db.scalar(
        select(Activity).where(
            Activity.id == activity_id, Activity.athlete_id == athlete_id, Activity.provider == "manual_fit"
        )
    )
    if activity is None:
        raise HTTPException(404, "Archivo no disponible")
    try:
        content = await read_file(f"fit/{athlete_id}/{activity.file_hash}.fit")
    except ObjectStoreError:
        raise HTTPException(404, "Archivo no disponible") from None
    return Response(
        content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": 'attachment; filename="actividad.fit"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
