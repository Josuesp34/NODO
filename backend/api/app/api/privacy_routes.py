"""Privacy, notification and administrative reads; mount before legacy product routes."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_superuser, current_user
from app.api.privacy_schemas import (
    OrganizationStatus,
    PreferencesUpdate,
    PurposeGrant,
    PushRegistration,
    PushSubscriptionView,
    SubscriptionStatus,
)
from app.api.product_schemas import ConsentView, DeleteAccount, PaymentCreate, PlanCreate, SubscriptionCreate
from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password
from app.infrastructure.database.models import User
from app.infrastructure.database.models.privacy import NotificationDelivery, NotificationPreference, PushSubscription
from app.infrastructure.database.models.product import (
    CoachAthleteAssignment,
    CommercialPlan,
    Consent,
    ManagedPayment,
    Organization,
    OrganizationMembership,
    Subscription,
)
from app.services.audit import add_audit
from app.services.notifications import explicit_push_consent, push_ready, register_subscription
from app.services.privacy import PURPOSES, erase_account, export_account_data, revoke_purpose, schedule_retention

router = APIRouter(tags=["Privacy and notifications"])


@router.get("/privacy/purposes")
async def consent_purposes(user: User = Depends(current_user)):
    return [
        {"scope": scope, "version": "pilot-v1", "description": description} for scope, description in PURPOSES.items()
    ]


@router.get("/consents", response_model=list[ConsentView])
async def list_consents(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return (
        await db.scalars(
            select(Consent).where(Consent.user_id == user.id).order_by(Consent.granted_at.desc(), Consent.id.desc())
        )
    ).all()


@router.post("/consents", response_model=ConsentView, status_code=201)
async def grant_consent(payload: PurposeGrant, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    consent = await db.scalar(
        select(Consent).where(
            Consent.user_id == user.id, Consent.scope == payload.scope, Consent.version == payload.version
        )
    )
    if consent is None:
        consent = Consent(user_id=user.id, scope=payload.scope, version=payload.version, granted_at=datetime.now(UTC))
        db.add(consent)
    else:
        consent.granted_at, consent.revoked_at = datetime.now(UTC), None
    await db.flush()
    add_audit(
        db,
        actor_id=user.id,
        entity="consent",
        entity_id=consent.id,
        action="grant",
        after={"scope": payload.scope, "version": payload.version},
    )
    await db.commit()
    return consent


@router.delete("/consents/{consent_id}", status_code=204)
async def revoke_consent(consent_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    row = await db.scalar(select(Consent).where(Consent.id == consent_id, Consent.user_id == user.id))
    if row is None:
        raise HTTPException(404, "Consentimiento no encontrado")
    await revoke_purpose(db, user, row)
    await db.commit()
    return Response(status_code=204)


@router.get("/notification-preferences")
async def preferences(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    row = await db.get(NotificationPreference, user.id)
    return {
        "preferences": PreferencesUpdate.model_validate(row) if row else PreferencesUpdate(timezone=user.timezone),
        "push_available": push_ready(),
        "public_key": getattr(settings, "WEB_PUSH_PUBLIC_KEY", "") if push_ready() else None,
    }


@router.put("/notification-preferences", response_model=PreferencesUpdate)
async def update_preferences(
    payload: PreferencesUpdate, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    if payload.enabled and not await explicit_push_consent(db, user.id):
        raise HTTPException(403, "CONSENT_REQUIRED:web_push")
    row = await db.get(NotificationPreference, user.id)
    if row is None:
        row = NotificationPreference(user_id=user.id)
        db.add(row)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    await db.commit()
    return row


@router.get("/push-subscriptions", response_model=list[PushSubscriptionView])
async def subscriptions(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return (
        await db.scalars(
            select(PushSubscription).where(PushSubscription.user_id == user.id).order_by(PushSubscription.id)
        )
    ).all()


@router.post("/push-subscriptions", response_model=PushSubscriptionView, status_code=201)
async def subscribe(payload: PushRegistration, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    row = await register_subscription(db, user, payload.model_dump())
    await db.commit()
    return row


@router.delete("/push-subscriptions/{subscription_id}", status_code=204)
async def unsubscribe(subscription_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    row = await db.scalar(
        select(PushSubscription).where(PushSubscription.id == subscription_id, PushSubscription.user_id == user.id)
    )
    if row is None:
        raise HTTPException(404, "Suscripción no encontrada")
    row.subscription_enc, row.revoked_at = None, datetime.now(UTC)
    await db.execute(
        update(NotificationDelivery)
        .where(NotificationDelivery.subscription_id == row.id, NotificationDelivery.status == "queued")
        .values(status="cancelled")
    )
    await db.commit()
    return Response(status_code=204)


@router.get("/account/export")
async def export_account(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await export_account_data(db, user)


@router.delete("/account", status_code=204)
async def delete_account(
    payload: DeleteAccount, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(401, "Contraseña incorrecta")
    await erase_account(db, user)
    await db.commit()
    return Response(status_code=204)


@router.get("/account/retention")
async def retention_policy(user: User = Depends(current_user)):
    return {
        "data_days": settings.DATA_RETENTION_DAYS,
        "outbox_days": getattr(settings, "RETENTION_OUTBOX_DAYS", 7),
        "job_interval_hours": getattr(settings, "RETENTION_JOB_INTERVAL_HOURS", 24),
        "backups": "Los backups expiran según la política de almacenamiento; no se reescriben durante el borrado.",
        "financial_records": "Los registros de organización se conservan separados de la identidad desidentificada.",
    }


@router.post("/admin/privacy/retention", status_code=202)
async def enqueue_retention(admin: User = Depends(current_superuser), db: AsyncSession = Depends(get_db)):
    await schedule_retention(db)
    await db.commit()
    return {"status": "queued"}


@router.get("/admin/commercial/catalog")
async def commercial_catalog(admin: User = Depends(current_superuser), db: AsyncSession = Depends(get_db)):
    organizations = (await db.scalars(select(Organization).order_by(Organization.name, Organization.id))).all()
    plans = (await db.scalars(select(CommercialPlan).order_by(CommercialPlan.name, CommercialPlan.id))).all()
    rows = (await db.scalars(select(Subscription).order_by(Subscription.id))).all()
    payments = (
        await db.scalars(select(ManagedPayment).order_by(ManagedPayment.paid_on.desc(), ManagedPayment.id.desc()))
    ).all()
    capacities = {}
    for org in organizations:
        capacities[org.id] = await db.scalar(
            select(func.count(func.distinct(CoachAthleteAssignment.athlete_id))).where(
                CoachAthleteAssignment.organization_id == org.id, CoachAthleteAssignment.status == "active"
            )
        )
    return {
        "organizations": [
            {"id": org.id, "name": org.name, "status": org.status, "active_athletes": capacities[org.id]}
            for org in organizations
        ],
        "plans": [
            {
                "id": plan.id,
                "name": plan.name,
                "athlete_limit": plan.athlete_limit,
                "active": plan.active,
                "monthly_price_cents": plan.monthly_price_cents,
                "currency": plan.currency,
            }
            for plan in plans
        ],
        "subscriptions": [
            {
                "id": row.id,
                "organization_id": row.organization_id,
                "plan_id": row.plan_id,
                "status": row.status,
                "starts_on": row.starts_on,
                "ends_on": row.ends_on,
            }
            for row in rows
        ],
        "payments": [
            {
                "id": row.id,
                "subscription_id": row.subscription_id,
                "amount_cents": row.amount_cents,
                "currency": row.currency,
                "paid_on": row.paid_on,
                "reference": row.reference,
            }
            for row in payments
        ],
    }


@router.post("/admin/commercial/plans", status_code=201)
async def create_commercial_plan(
    payload: PlanCreate, admin: User = Depends(current_superuser), db: AsyncSession = Depends(get_db)
):
    values = payload.model_dump()
    values["name"] = payload.name.strip()
    if not values["name"]:
        raise HTTPException(422, "El nombre no puede estar vacío")
    if payload.currency is not None:
        currency = payload.currency.upper()
        if not currency.isalpha() or not currency.isascii():
            raise HTTPException(422, "Moneda inválida")
        values["currency"] = currency
    row = CommercialPlan(**values)
    db.add(row)
    try:
        await db.flush()
        add_audit(db, actor_id=admin.id, entity="commercial_plan", entity_id=row.id, action="create")
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Ya existe un plan con este nombre") from None
    return {"id": row.id}


@router.post("/admin/commercial/subscriptions", status_code=201)
async def create_subscription(
    payload: SubscriptionCreate, admin: User = Depends(current_superuser), db: AsyncSession = Depends(get_db)
):
    if payload.ends_on and payload.ends_on < payload.starts_on:
        raise HTTPException(422, "El fin debe ser posterior o igual al inicio")
    org = await db.scalar(select(Organization).where(Organization.id == payload.organization_id).with_for_update())
    plan = await db.get(CommercialPlan, payload.plan_id)
    if org is None or plan is None:
        raise HTTPException(404, "Organización o plan no encontrado")
    if org.status != "active" or not plan.active:
        raise HTTPException(409, "Organización o plan inactivo")
    count = await db.scalar(
        select(func.count(func.distinct(CoachAthleteAssignment.athlete_id))).where(
            CoachAthleteAssignment.organization_id == org.id, CoachAthleteAssignment.status == "active"
        )
    )
    if count > plan.athlete_limit:
        raise HTTPException(409, "El plan tiene menos cupos que atletas activos")
    row = await db.scalar(select(Subscription).where(Subscription.organization_id == org.id))
    if row is None:
        row = Subscription(status="active", **payload.model_dump())
        db.add(row)
    else:
        for name, value in payload.model_dump().items():
            setattr(row, name, value)
        row.status = "active"
    await db.flush()
    add_audit(db, actor_id=admin.id, entity="subscription", entity_id=row.id, action="activate")
    await db.commit()
    return {"id": row.id, "status": row.status}


@router.post("/admin/commercial/payments", status_code=201)
async def record_payment(
    payload: PaymentCreate, admin: User = Depends(current_superuser), db: AsyncSession = Depends(get_db)
):
    row = await db.scalar(select(Subscription).where(Subscription.id == payload.subscription_id).with_for_update())
    if row is None:
        raise HTTPException(404, "Suscripción no encontrada")
    plan = await db.get(CommercialPlan, row.plan_id)
    currency = payload.currency.upper()
    if not currency.isalpha() or not currency.isascii() or payload.amount_cents <= 0:
        raise HTTPException(422, "Importe o moneda inválidos")
    if plan.currency and currency != plan.currency.upper():
        raise HTTPException(422, "La moneda no corresponde al plan")
    values = {**payload.model_dump(), "currency": currency, "reference": payload.reference.strip()}
    if not values["reference"]:
        raise HTTPException(422, "La referencia no puede estar vacía")
    existing = await db.scalar(select(ManagedPayment).where(ManagedPayment.reference == values["reference"]))
    if existing:
        if all(getattr(existing, name) == value for name, value in values.items()):
            return {"id": existing.id, "status": "recorded"}
        raise HTTPException(409, "La referencia pertenece a otro pago")
    payment = ManagedPayment(recorded_by=admin.id, **values)
    db.add(payment)
    try:
        await db.flush()
        add_audit(db, actor_id=admin.id, entity="managed_payment", entity_id=payment.id, action="record")
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "La referencia pertenece a otro pago") from None
    return {"id": payment.id, "status": "recorded"}


@router.get("/commercial/status")
async def my_commercial_status(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    org_ids = (
        await db.scalars(
            select(OrganizationMembership.organization_id).where(
                OrganizationMembership.user_id == user.id, OrganizationMembership.status == "active"
            )
        )
    ).all()
    rows = (
        await db.execute(
            select(Organization, Subscription, CommercialPlan)
            .outerjoin(Subscription, Subscription.organization_id == Organization.id)
            .outerjoin(CommercialPlan, CommercialPlan.id == Subscription.plan_id)
            .where(Organization.id.in_(org_ids))
        )
    ).all()
    return [
        {
            "organization": org.name,
            "status": org.status,
            "subscription_status": subscription.status if subscription else None,
            "plan": plan.name if plan else None,
            "athlete_limit": plan.athlete_limit if plan else None,
        }
        for org, subscription, plan in rows
    ]


@router.patch("/admin/organizations/{organization_id}")
async def organization_status(
    organization_id: int,
    payload: OrganizationStatus,
    admin: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_db),
):
    org = await db.scalar(select(Organization).where(Organization.id == organization_id).with_for_update())
    if org is None:
        raise HTTPException(404, "Organización no encontrada")
    org.status = payload.status
    add_audit(
        db,
        actor_id=admin.id,
        entity="organization",
        entity_id=org.id,
        action=payload.status,
        after={"reason": payload.reason},
    )
    await db.commit()
    return {"id": org.id, "status": org.status}


@router.patch("/admin/commercial/subscriptions/{subscription_id}")
async def subscription_status(
    subscription_id: int,
    payload: SubscriptionStatus,
    admin: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_db),
):
    row = await db.scalar(select(Subscription).where(Subscription.id == subscription_id).with_for_update())
    if row is None:
        raise HTTPException(404, "Suscripción no encontrada")
    row.status = payload.status
    add_audit(
        db,
        actor_id=admin.id,
        entity="subscription",
        entity_id=row.id,
        action=payload.status,
        after={"reason": payload.reason},
    )
    await db.commit()
    return {"id": row.id, "status": row.status}
