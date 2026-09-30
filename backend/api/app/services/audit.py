from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.product import AuditLog


def add_audit(
    db: AsyncSession,
    *,
    actor_id: int | None,
    entity: str,
    entity_id: int | str,
    action: str,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            entity=entity,
            entity_id=str(entity_id),
            action=action,
            before=before,
            after=after,
            at=datetime.now(UTC),
        )
    )
