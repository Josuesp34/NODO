"""Purpose enforcement and FK-aware erasure. No credentials are part of an export."""

import json
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.database.models import Base, User
from app.infrastructure.database.models.privacy import (
    NotificationDelivery,
    NotificationPreference,
    PrivacyArtifact,
    PushSubscription,
)
from app.infrastructure.database.models.product import (
    AssistantConfirmation,
    AssistantMessage,
    AssistantThread,
    AthleteConnection,
    AuditLog,
    Consent,
    Job,
    Organization,
    OrganizationMembership,
)

PURPOSES = {
    "training_data_processing": "Actividades, telemetría y seguimiento deportivo",
    "ai_assistant": "Consultas al asistente con contexto deportivo mínimo",
    "web_push": "Avisos genéricos en este dispositivo, sin métricas ni nombres",
}


async def require_processing_consent(db: AsyncSession, user_id: int, scope: str) -> None:
    consent = await db.scalar(
        select(Consent)
        .where(Consent.user_id == user_id, Consent.scope == scope, Consent.version == "pilot-v1")
        .order_by(Consent.granted_at.desc(), Consent.id.desc())
        .limit(1)
    )
    if consent is not None and consent.revoked_at is None:
        return
    # Local fixtures may omit consent, but an explicit withdrawal always applies.
    if consent is None and settings.ENVIRONMENT == "development":
        if (
            await db.scalar(select(Consent.id).where(Consent.user_id == user_id, Consent.scope == scope).limit(1))
            is None
        ):
            return
    raise HTTPException(403, f"CONSENT_REQUIRED:{scope}")


def references_user(value, user_id: int) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                key in {"user_id", "athlete_id", "coach_id", "owner_id", "recipient_id", "athlete_scope_id"}
                and item == user_id
            ):
                return True
            if key in {"athlete_ids", "user_ids"} and isinstance(item, list) and user_id in item:
                return True
            if references_user(item, user_id):
                return True
    elif isinstance(value, list):
        return any(references_user(item, user_id) for item in value)
    return False


async def cancel_user_processing(db: AsyncSession, user_id: int, *, email: str | None = None) -> None:
    """Cancel linked jobs; legacy email jobs are linked through their opaque dedupe keys."""
    from app.infrastructure.database.models import AthleteInvitation, PasswordReset

    invitation_ids = (
        await db.scalars(select(AthleteInvitation.id).where(AthleteInvitation.athlete_id == user_id))
    ).all()
    reset_ids = (await db.scalars(select(PasswordReset.id).where(PasswordReset.user_id == user_id))).all()
    delivery_ids = (
        await db.scalars(select(NotificationDelivery.id).where(NotificationDelivery.user_id == user_id))
    ).all()
    keys = {f"nodo-invitation-{item}" for item in invitation_ids} | {
        f"nodo-password-reset-{item}" for item in reset_ids
    }
    jobs = (await db.scalars(select(Job).with_for_update())).all()
    for job in jobs:
        linked = (
            references_user(job.payload, user_id)
            or job.dedupe_key in keys
            or job.payload.get("delivery_id") in delivery_ids
        )
        if email and job.kind == "send_resend_email" and job.payload.get("ciphertext") and settings.EMAIL_QUEUE_KEY:
            from cryptography.fernet import Fernet, InvalidToken

            try:
                message = json.loads(
                    Fernet(settings.EMAIL_QUEUE_KEY.encode()).decrypt(job.payload["ciphertext"].encode())
                )
                linked = linked or message.get("to", "").lower() == email.lower()
            except (ValueError, InvalidToken, KeyError, TypeError):
                # The dedupe relation is sufficient for invitations and password recovery.
                pass
        if linked:
            await db.delete(job)


async def revoke_purpose(db: AsyncSession, user: User, consent: Consent) -> None:
    consent.revoked_at = datetime.now(UTC)
    if consent.scope in {"web_push", "training_data_processing"}:
        await db.execute(
            update(PushSubscription)
            .where(PushSubscription.user_id == user.id)
            .values(subscription_enc=None, revoked_at=datetime.now(UTC))
        )
        await db.execute(
            update(NotificationDelivery)
            .where(NotificationDelivery.user_id == user.id, NotificationDelivery.status == "queued")
            .values(status="cancelled")
        )
        await db.execute(
            update(NotificationPreference).where(NotificationPreference.user_id == user.id).values(enabled=False)
        )
    if consent.scope == "training_data_processing":
        await queue_remote_revocations(db, user.id)
        await cancel_user_processing(db, user.id)
        await db.execute(
            update(AthleteConnection)
            .where(AthleteConnection.athlete_id == user.id)
            .values(status="revoked", access_token_enc=None, refresh_token_enc=None, scopes=[])
        )
        # Provider-specific ephemeral authorization state is not retained after withdrawal.
        for table in Base.metadata.sorted_tables:
            if "oauth" in table.name and "state" in table.name:
                predicates = [
                    column == user.id
                    for column in table.columns
                    if column.name in {"user_id", "athlete_id", "owner_id"}
                ]
                if predicates:
                    await db.execute(delete(table).where(or_(*predicates)))
            if table.name == "provider_records" and "athlete_id" in table.c:
                await db.execute(delete(table).where(table.c.athlete_id == user.id))
        observations = Base.metadata.tables["observations"]
        await db.execute(
            delete(observations).where(
                observations.c.athlete_id == user.id, observations.c.source.in_(["intervals", "intervals_icu"])
            )
        )
    if consent.scope in {"ai_assistant", "training_data_processing"}:
        confirmations = Base.metadata.tables["assistant_confirmations"]
        await db.execute(delete(confirmations).where(confirmations.c.user_id == user.id))
    db.add(
        AuditLog(actor_id=user.id, entity="consent", entity_id=str(consent.id), action="revoke", at=datetime.now(UTC))
    )


async def _owned_ids(db: AsyncSession, user_id: int) -> dict[str, set[int]]:
    selected: dict[str, set[int]] = {}
    excluded = {"users", "audit_log", "managed_payments", "privacy_artifacts"}
    owner_columns = {"athlete_id", "user_id", "owner_id", "coach_id", "actor_id", "athlete_scope_id"}
    for table in Base.metadata.sorted_tables:
        if table.name in excluded or len(table.primary_key.columns) != 1:
            continue
        pk = next(iter(table.primary_key.columns))
        predicates = [
            column == user_id
            for column in table.columns
            if column.name in owner_columns and any(fk.target_fullname == "users.id" for fk in column.foreign_keys)
        ]
        if predicates:
            selected[table.name] = set((await db.scalars(select(pk).where(or_(*predicates)))).all())
    # General coach chats may contain derived athlete facts in prose. Erase the
    # entire affected conversation rather than leaving prose after stripping citations.
    messages = (await db.scalars(select(AssistantMessage))).all()
    for message in messages:
        if references_user(message.citations, user_id):
            selected.setdefault("assistant_threads", set()).add(message.thread_id)
    for confirmation in (await db.scalars(select(AssistantConfirmation))).all():
        if references_user(confirmation.payload, user_id) or references_user(confirmation.result, user_id):
            selected.setdefault("assistant_threads", set()).add(confirmation.thread_id)
    changed = True
    while changed:
        changed = False
        for table in Base.metadata.sorted_tables:
            if table.name in excluded or len(table.primary_key.columns) != 1:
                continue
            pk = next(iter(table.primary_key.columns))
            for column in table.columns:
                for fk in column.foreign_keys:
                    parent = fk.column.table.name
                    if parent in selected and selected[parent] and fk.ondelete != "SET NULL":
                        ids = set((await db.scalars(select(pk).where(column.in_(selected[parent])))).all())
                        known = selected.setdefault(table.name, set())
                        if ids - known:
                            known.update(ids)
                            changed = True
    return selected


async def erase_account(db: AsyncSession, user: User) -> dict:
    """Tombstone retains only identity needed by financial FKs, never login or PII."""
    from app.core.security import hash_password

    # Serialize deletion with notification delivery and scoped writes taking this lock.
    await db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    await queue_remote_revocations(db, user.id)
    await cancel_user_processing(db, user.id, email=user.email)
    selected = await _owned_ids(db, user.id)
    # User budget counters have a polymorphic key rather than a foreign key.
    for table in Base.metadata.sorted_tables:
        if "budget" in table.name and {"scope", "scope_id"}.issubset(table.c.keys()):
            from sqlalchemy import String, cast

            await db.execute(
                delete(table).where(table.c.scope == "user", cast(table.c.scope_id, String) == str(user.id))
            )
    owned_orgs = (
        await db.scalars(
            select(OrganizationMembership.organization_id).where(
                OrganizationMembership.user_id == user.id, OrganizationMembership.role == "owner"
            )
        )
    ).all()
    for organization_id in owned_orgs:
        other_owner = await db.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.user_id != user.id,
                OrganizationMembership.role == "owner",
                OrganizationMembership.status == "active",
            )
        )
        if other_owner is None:
            await db.execute(update(Organization).where(Organization.id == organization_id).values(status="suspended"))
    artifacts = (await db.scalars(select(PrivacyArtifact).where(PrivacyArtifact.user_id == user.id))).all()
    for artifact in artifacts:
        artifact.status = "delete_pending"
        if await db.scalar(select(Job.id).where(Job.dedupe_key == f"erase-file:{artifact.id}")) is None:
            db.add(
                Job(
                    kind="privacy_delete_file",
                    payload={"artifact_id": artifact.id},
                    run_after=datetime.now(UTC),
                    max_attempts=settings.JOB_MAX_ATTEMPTS,
                    dedupe_key=f"erase-file:{artifact.id}",
                )
            )
    db.add(
        Job(
            kind="privacy_delete_user_files",
            payload={"user_id": user.id},
            run_after=datetime.now(UTC),
            max_attempts=settings.JOB_MAX_ATTEMPTS,
            dedupe_key=f"erase-user-files:{user.id}",
        )
    )
    # Erase narrative audit data concerning this user or their removed entities.
    for audit in (await db.scalars(select(AuditLog))).all():
        aliases = {
            "workout": "prescribed_workouts",
            "block": "training_blocks",
            "profile": "athlete_profiles",
            "template": "plan_templates",
            "group": "athlete_groups",
        }
        related_table = aliases.get(audit.entity, audit.entity if audit.entity in selected else f"{audit.entity}s")
        related_record = audit.entity_id.isdecimal() and int(audit.entity_id) in selected.get(related_table, set())
        if (
            audit.actor_id == user.id
            or related_record
            or references_user(audit.before, user.id)
            or references_user(audit.after, user.id)
            or (audit.entity in {"user", "athlete", "athlete_invitation"} and audit.entity_id == str(user.id))
        ):
            await db.delete(audit)
    # SET NULL relations belong to other accounts and remain usable.
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            for fk in column.foreign_keys:
                parent = fk.column.table.name
                if fk.ondelete == "SET NULL" and parent in selected and selected[parent]:
                    await db.execute(update(table).where(column.in_(selected[parent])).values({column.name: None}))
    review = Base.metadata.tables["review_items"]
    await db.execute(update(review).where(review.c.decided_by == user.id).values(decided_by=None, decision_note=None))
    await db.execute(update(User).where(User.coach_id == user.id).values(coach_id=None))
    counts = {}
    for table in reversed(Base.metadata.sorted_tables):
        ids = selected.get(table.name)
        if ids:
            pk = next(iter(table.primary_key.columns))
            result = await db.execute(delete(table).where(pk.in_(ids)))
            counts[table.name] = result.rowcount
    from app.services.rate_limit import _hash

    limits = Base.metadata.tables["auth_rate_limits"]
    await db.execute(
        delete(limits).where(
            limits.c.key_hash.in_(
                [_hash(scope, user.email) for scope in ("login", "password-reset", "password-reset-confirm")]
            )
        )
    )
    user.email = f"deleted-{user.id}-{secrets.token_hex(6)}@invalid.local"
    user.first_name, user.last_name, user.timezone = "Cuenta", "eliminada", "UTC"
    user.hashed_password = hash_password(secrets.token_urlsafe(48))
    user.is_superuser = False
    user.email_verified_at = None
    user.deleted_at = datetime.now(UTC)
    user.coach_id = None
    return {"deleted": counts, "files_pending": len(artifacts), "identity": "deidentified"}


async def queue_remote_revocations(db: AsyncSession, user_id: int) -> None:
    try:
        from app.services.intervals_real import queue_remote_disconnect
    except ImportError:
        # The legacy/simulator branch cannot issue a real OAuth connection. Root
        # integrates the real adapter before enabling providers.
        return
    for connection in (
        await db.scalars(
            select(AthleteConnection).where(
                AthleteConnection.athlete_id == user_id, AthleteConnection.access_token_enc.is_not(None)
            )
        )
    ).all():
        await queue_remote_disconnect(db, connection)


async def export_account_data(db: AsyncSession, user: User) -> dict:
    from app.services.access import has_athlete_access
    from app.services.assistant import assistant_message_view

    selected = await _owned_ids(db, user.id)
    excluded = {
        "auth_sessions",
        "athlete_invitations",
        "password_resets",
        "push_subscriptions",
        "assistant_confirmations",
        "athlete_connections",
        "assistant_messages",
        "assistant_threads",
    }
    data = {}
    secrets_columns = {
        "hashed_password",
        "token_hash",
        "access_hash",
        "refresh_hash",
        "payload_hash",
        "subscription_enc",
        "locator_enc",
        "access_token_enc",
        "refresh_token_enc",
        "endpoint_hash",
    }
    visible_ids = {}
    for table in Base.metadata.sorted_tables:
        name = table.name
        ids = selected.get(name, set())
        if name in excluded or "oauth" in name or "provider" in name or not ids:
            continue
        pk = next(iter(table.primary_key.columns))
        rows = (await db.execute(select(table).where(pk.in_(ids)).order_by(pk))).mappings().all()
        visible_rows = []
        for row in rows:
            if row.get("user_id") and row["user_id"] != user.id:
                continue
            if (
                row.get("athlete_id")
                and row["athlete_id"] != user.id
                and not await has_athlete_access(db, user, row["athlete_id"])
            ):
                continue
            if any(
                fk.column.table.name in visible_ids
                and row[column.name] is not None
                and row[column.name] not in visible_ids[fk.column.table.name]
                for column in table.c
                for fk in column.foreign_keys
            ):
                continue
            visible_rows.append(row)
        visible_ids[name] = {row[pk.name] for row in visible_rows}
        data[name] = [
            {
                key: value
                for key, value in row.items()
                if key not in secrets_columns
                and "token" not in key
                and "secret" not in key
                and not key.endswith("_enc")
            }
            for row in visible_rows
        ]
    messages = []
    for thread in (await db.scalars(select(AssistantThread).where(AssistantThread.owner_id == user.id))).all():
        if thread.athlete_scope_id not in (None, user.id) and not await has_athlete_access(
            db, user, thread.athlete_scope_id
        ):
            continue
        for message in (
            await db.scalars(
                select(AssistantMessage)
                .where(AssistantMessage.thread_id == thread.id)
                .order_by(AssistantMessage.created_at, AssistantMessage.id)
            )
        ).all():
            own_context = thread.athlete_scope_id == user.id or (
                thread.role == "athlete" and thread.athlete_scope_id is None
            )
            own_citations = all(
                isinstance(citation, dict)
                and isinstance(citation.get("athlete_id"), int)
                and not isinstance(citation.get("athlete_id"), bool)
                and citation["athlete_id"] == user.id
                for citation in message.citations or []
            )
            # A data subject can export their prior personal data after withdrawing
            # processing consent; this exception grants no access to another athlete.
            visible = (
                {"author": message.author, "content": message.content, "created_at": message.created_at}
                if own_context and own_citations
                else await assistant_message_view(db, user, message)
            )
            messages.append({key: visible[key] for key in ("author", "content", "created_at")})
    data["assistant_messages"] = messages
    connections = (await db.scalars(select(AthleteConnection).where(AthleteConnection.athlete_id == user.id))).all()
    data["connections"] = [
        {"provider": item.provider, "status": item.status, "scopes": item.scopes, "last_sync_at": item.last_sync_at}
        for item in connections
    ]
    data["user"] = {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "timezone": user.timezone,
    }
    data["generated_at"] = datetime.now(UTC)
    data["files"] = [
        {"id": item.id, "status": item.status}
        for item in (await db.scalars(select(PrivacyArtifact).where(PrivacyArtifact.user_id == user.id))).all()
    ]
    return data


async def sweep_retention(db: AsyncSession, *, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=settings.DATA_RETENTION_DAYS)
    counts = {}
    # Event time, not mutable updated_at, determines retention of source records.
    timestamp_columns = {
        "activities": "start_time",
        "observations": "observed_end",
        "checkins": "local_date",
        "complaints": "started_on",
        "daily_load": "local_date",
        "daily_physiology": "date_recorded",
        "assistant_messages": "created_at",
        "assistant_confirmations": "expires_at",
        "ingestion_events": "created_at",
        "notification_deliveries": "created_at",
        "prescribed_workouts": "scheduled_date",
        "competitions": "competition_date",
        "recommendations": "created_at",
        "review_items": "created_at",
        "athlete_profiles": "valid_to",
        "assistant_runs": "created_at",
        "provider_records": "created_at",
    }
    for name, column_name in timestamp_columns.items():
        table = Base.metadata.tables.get(name)
        if table is None or column_name not in table.c:
            continue
        limit = (
            cutoff.date()
            if column_name in {"local_date", "date_recorded", "started_on", "competition_date", "valid_to"}
            else cutoff
        )
        if name == "assistant_confirmations":
            limit = now
        result = await db.execute(delete(table).where(table.c[column_name] < limit))
        counts[name] = result.rowcount
    blocks = Base.metadata.tables["training_blocks"]
    workouts = Base.metadata.tables["prescribed_workouts"]
    # A bad/legacy block date cannot remove a still-retained child's plan.
    counts["training_blocks"] = (
        await db.execute(
            delete(blocks).where(
                blocks.c.end_date < cutoff.date(),
                ~select(workouts.c.id).where(workouts.c.block_id == blocks.c.id).exists(),
            )
        )
    ).rowcount
    # Titles can contain personal facts, so stale empty conversations also expire.
    counts["assistant_threads"] = (
        await db.execute(
            delete(AssistantThread).where(
                AssistantThread.updated_at < cutoff,
                ~select(AssistantMessage.id).where(AssistantMessage.thread_id == AssistantThread.id).exists(),
            )
        )
    ).rowcount
    for name in ("auth_sessions", "password_resets", "athlete_invitations"):
        table = Base.metadata.tables[name]
        column = table.c.refresh_expires_at if name == "auth_sessions" else table.c.expires_at
        if name != "auth_sessions":
            expired_ids = (await db.scalars(select(table.c.id).where(column < now))).all()
            prefix = "nodo-password-reset" if name == "password_resets" else "nodo-invitation"
            keys = [f"{prefix}-{item}" for item in expired_ids]
            counts[f"{name}_outbox"] = (await db.execute(delete(Job).where(Job.dedupe_key.in_(keys)))).rowcount
        counts[name] = (await db.execute(delete(table).where(column < now))).rowcount
    outbox_cutoff = now - timedelta(days=getattr(settings, "RETENTION_OUTBOX_DAYS", 7))
    # Expire old pending/dead email too; stale recovery codes must never deliver.
    counts["jobs"] = (
        await db.execute(
            delete(Job).where(
                Job.created_at < outbox_cutoff,
                Job.kind.not_in(["privacy_delete_file", "privacy_delete_user_files", "intervals_disconnect"]),
                Job.status != "running",
            )
        )
    ).rowcount
    for sub in (await db.scalars(select(PushSubscription).where(PushSubscription.expires_at < now))).all():
        sub.subscription_enc, sub.revoked_at = None, now
    counts["audit_log"] = (await db.execute(delete(AuditLog).where(AuditLog.at < cutoff))).rowcount
    return counts


async def schedule_retention(db: AsyncSession, *, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    bucket = int(now.timestamp()) // (3600 * getattr(settings, "RETENTION_JOB_INTERVAL_HOURS", 24))
    key = f"retention:{bucket}"
    if db.bind and db.bind.dialect.name == "postgresql":
        from sqlalchemy import text

        await db.execute(text("SELECT pg_advisory_xact_lock(781304902)"))
    if await db.scalar(select(Job.id).where(Job.dedupe_key == key)) is None:
        db.add(
            Job(
                kind="privacy_retention",
                payload={},
                run_after=now,
                max_attempts=settings.JOB_MAX_ATTEMPTS,
                dedupe_key=key,
            )
        )
