"""Build the sellable-pilot backend on PostgreSQL 16.

Revision ID: 0004_pilot_backend
Revises: 0003_align_indexes
Create Date: 2026-09-20

This migration intentionally supports the pre-pilot database only. It refuses to
guess an owner for legacy activities with a null athlete_id.
"""

import sqlalchemy as sa
from alembic import op

from app.infrastructure.database.models import Base

revision = "0004_pilot_backend"
down_revision = "0003_align_indexes"
branch_labels = None
depends_on = None


PILOT_TABLES = (
    "user_roles",
    "auth_rate_limits",
    "organizations",
    "organization_memberships",
    "coach_athlete_assignments",
    "athlete_profiles",
    "competitions",
    "activity_laps",
    "daily_load",
    "observations",
    "checkins",
    "complaints",
    "complaint_updates",
    "review_items",
    "athlete_groups",
    "group_memberships",
    "plan_templates",
    "plan_assignments",
    "ingestion_events",
    "jobs",
    "athlete_connections",
    "consents",
    "audit_log",
    "assistant_threads",
    "assistant_messages",
    "assistant_confirmations",
    "recommendations",
    "decisions",
    "commercial_plans",
    "subscriptions",
    "managed_payments",
)


def _convert_telemetry_to_partitions() -> None:
    op.rename_table("telemetry_records", "telemetry_records_legacy")
    op.create_table(
        "telemetry_records",
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heart_rate", sa.Integer()),
        sa.Column("speed_ms", sa.Float()),
        sa.Column("cadence", sa.Integer()),
        sa.Column("altitude", sa.Float()),
        sa.Column("power", sa.Integer()),
        sa.Column("temperature", sa.Integer()),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("activity_id", "timestamp"),
        postgresql_partition_by="RANGE (timestamp)",
    )
    op.execute("CREATE TABLE telemetry_records_default PARTITION OF telemetry_records DEFAULT")
    op.execute(
        "INSERT INTO telemetry_records SELECT activity_id, timestamp, heart_rate, speed_ms, cadence, "
        "altitude, power, temperature FROM telemetry_records_legacy"
    )
    op.drop_table("telemetry_records_legacy")
    op.create_index("telemetry_records_timestamp_idx", "telemetry_records", ["timestamp"], postgresql_using="brin")


def _convert_telemetry_to_regular() -> None:
    op.drop_index("telemetry_records_timestamp_idx", table_name="telemetry_records")
    op.rename_table("telemetry_records", "telemetry_records_partitioned")
    op.create_table(
        "telemetry_records",
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heart_rate", sa.Integer()),
        sa.Column("speed_ms", sa.Float()),
        sa.Column("cadence", sa.Integer()),
        sa.Column("altitude", sa.Float()),
        sa.Column("power", sa.Integer()),
        sa.Column("temperature", sa.Integer()),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("activity_id", "timestamp"),
    )
    op.execute(
        "INSERT INTO telemetry_records SELECT activity_id, timestamp, heart_rate, speed_ms, cadence, "
        "altitude, power, temperature FROM telemetry_records_partitioned"
    )
    op.execute("DROP TABLE telemetry_records_partitioned CASCADE")


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("activities", sa.Column("file_hash", sa.String(64), nullable=True))
    op.add_column("activities", sa.Column("provider", sa.String(40), nullable=False, server_default="manual_fit"))
    op.add_column("activities", sa.Column("external_id", sa.String(255), nullable=True))
    op.add_column("activities", sa.Column("sport_type", sa.String(40), nullable=False, server_default="running"))
    op.add_column("activities", sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"))
    op.add_column("activities", sa.Column("prescribed_workout_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_activity_workout",
        "activities",
        "prescribed_workouts",
        ["prescribed_workout_id"],
        ["id"],
        ondelete="SET NULL",
    )

    if is_postgres:
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM activities WHERE athlete_id IS NULL) THEN "
            "RAISE EXCEPTION 'Cannot migrate: activities without athlete owner'; END IF; END $$"
        )
        op.execute(
            "UPDATE activities SET file_hash = md5(file_name || ':' || id::text) || "
            "md5(id::text || ':' || file_name) WHERE file_hash IS NULL"
        )
    else:
        op.execute(
            "UPDATE activities SET file_hash = printf('%064d', id) WHERE file_hash IS NULL AND athlete_id IS NOT NULL"
        )
    op.alter_column("activities", "athlete_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("activities", "file_hash", existing_type=sa.String(64), nullable=False)
    op.create_unique_constraint("uq_activity_athlete_file_hash", "activities", ["athlete_id", "file_hash"])
    op.create_unique_constraint("uq_activity_provider_external_id", "activities", ["provider", "external_id"])
    op.drop_column("activities", "acwr")

    if is_postgres:
        _convert_telemetry_to_partitions()
        op.execute("DROP EXTENSION IF EXISTS timescaledb")

    for table_name in PILOT_TABLES:
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)

    if is_postgres:
        op.execute(
            "INSERT INTO user_roles (user_id, role, created_at, updated_at) "
            "SELECT id, CASE role::text WHEN 'COACH' THEN 'coach' ELSE 'athlete' END, now(), now() "
            "FROM users ON CONFLICT DO NOTHING"
        )
        op.execute(
            "INSERT INTO organizations (name, slug, status, created_at, updated_at) "
            "SELECT first_name || ' ' || last_name, 'legacy-coach-' || id::text, 'active', now(), now() "
            "FROM users WHERE role::text = 'COACH' ON CONFLICT DO NOTHING"
        )
        op.execute(
            "INSERT INTO organization_memberships (organization_id, user_id, role, status, created_at, updated_at) "
            "SELECT o.id, u.id, 'owner', 'active', now(), now() FROM users u "
            "JOIN organizations o ON o.slug = 'legacy-coach-' || u.id::text "
            "WHERE u.role::text = 'COACH' ON CONFLICT DO NOTHING"
        )
        op.execute(
            "INSERT INTO coach_athlete_assignments "
            "(organization_id, coach_id, athlete_id, status, created_at, updated_at) "
            "SELECT o.id, a.coach_id, a.id, 'active', now(), now() FROM users a "
            "JOIN organizations o ON o.slug = 'legacy-coach-' || a.coach_id::text "
            "WHERE a.coach_id IS NOT NULL ON CONFLICT DO NOTHING"
        )
        op.execute(
            "INSERT INTO organization_memberships "
            "(organization_id, user_id, role, status, created_at, updated_at) "
            "SELECT ca.organization_id, ca.athlete_id, 'athlete', 'active', now(), now() "
            "FROM coach_athlete_assignments ca WHERE ca.organization_id IS NOT NULL ON CONFLICT DO NOTHING"
        )
        op.execute(
            "INSERT INTO observations "
            "(athlete_id, metric_type, value, unit, method, source, observed_start, observed_end, "
            "received_at, timezone, quality, created_at, updated_at) "
            "SELECT athlete_id, 'hrv', rmssd, 'ms', 'RMSSD', 'legacy_daily_physiology', "
            "date_recorded::timestamp AT TIME ZONE 'UTC', date_recorded::timestamp AT TIME ZONE 'UTC', "
            "now(), 'UTC', 'legacy_unknown', now(), now() FROM daily_physiology WHERE rmssd IS NOT NULL "
            "UNION ALL SELECT athlete_id, 'resting_hr', resting_hr, 'bpm', 'unknown', "
            "'legacy_daily_physiology', date_recorded::timestamp AT TIME ZONE 'UTC', "
            "date_recorded::timestamp AT TIME ZONE 'UTC', now(), 'UTC', 'legacy_unknown', now(), now() "
            "FROM daily_physiology WHERE resting_hr IS NOT NULL"
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in reversed(PILOT_TABLES):
        table = Base.metadata.tables[table_name]
        table.drop(bind=bind, checkfirst=True)
    if bind.dialect.name == "postgresql":
        _convert_telemetry_to_regular()
    op.add_column("activities", sa.Column("acwr", sa.Float(), nullable=True))
    op.drop_constraint("uq_activity_provider_external_id", "activities", type_="unique")
    op.drop_constraint("uq_activity_athlete_file_hash", "activities", type_="unique")
    op.drop_constraint("fk_activity_workout", "activities", type_="foreignkey")
    for column in ("prescribed_workout_id", "timezone", "sport_type", "external_id", "provider", "file_hash"):
        op.drop_column("activities", column)
    op.alter_column("activities", "athlete_id", existing_type=sa.Integer(), nullable=True)
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "email_verified_at")
