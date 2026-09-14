"""Create the NODO core schema for new environments.

Revision ID: 0001_nodo_core
Revises:
Create Date: 2026-09-13
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_nodo_core"
down_revision = None
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
    role = sa.Enum("COACH", "ATHLETE", name="userrole")
    op.create_table(
        "users", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False), sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False), sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("timezone", sa.String(64), server_default="UTC", nullable=False),
        sa.Column("role", role, nullable=False), sa.Column("coach_id", sa.Integer(), sa.ForeignKey("users.id")), *timestamps(),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "activities", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("file_name", sa.String(255), nullable=False), sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_duration_sec", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_distance_m", sa.Float(), nullable=False, server_default="0"), sa.Column("avg_heart_rate", sa.Integer()),
        sa.Column("max_heart_rate", sa.Integer()), sa.Column("avg_speed_mps", sa.Float()), sa.Column("total_elevation_gain_m", sa.Float()),
        sa.Column("calculated_trimp", sa.Float()), sa.Column("calculated_tss", sa.Float()), sa.Column("ctl", sa.Float()),
        sa.Column("atl", sa.Float()), sa.Column("tsb", sa.Float()), sa.Column("acwr", sa.Float()), *timestamps(),
    )
    op.create_index("ix_activities_start_time", "activities", ["start_time"])
    op.create_table(
        "telemetry_records", sa.Column("activity_id", sa.Integer(), sa.ForeignKey("activities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False), sa.Column("heart_rate", sa.Integer()),
        sa.Column("speed_ms", sa.Float()), sa.Column("cadence", sa.Integer()), sa.Column("altitude", sa.Float()),
        sa.Column("power", sa.Integer()), sa.Column("temperature", sa.Integer()), sa.PrimaryKeyConstraint("activity_id", "timestamp"),
    )
    op.create_table(
        "daily_physiology", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date_recorded", sa.Date(), nullable=False), sa.Column("rmssd", sa.Float()), sa.Column("resting_hr", sa.Integer()),
        sa.Column("sleep_score", sa.Integer()), sa.Column("sleep_duration_hours", sa.Float()), sa.Column("perceived_stress", sa.Integer()),
        sa.UniqueConstraint("athlete_id", "date_recorded", name="uix_athlete_date"), *timestamps(),
    )
    op.create_table(
        "auth_sessions", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("access_hash", sa.String(64), unique=True, nullable=False), sa.Column("refresh_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_table(
        "athlete_invitations", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "training_blocks", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("coach_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("title", sa.String(255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False), sa.Column("end_date", sa.Date(), nullable=False), *timestamps(),
    )
    op.create_index("ix_training_blocks_athlete_id", "training_blocks", ["athlete_id"])
    op.create_index("ix_training_blocks_coach_id", "training_blocks", ["coach_id"])
    op.create_table(
        "prescribed_workouts", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("coach_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.String()), sa.Column("scheduled_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_duration_sec", sa.Float()), sa.Column("target_tss", sa.Float()), sa.Column("target_trimp", sa.Float()),
        sa.Column("sport_type", sa.String(50), nullable=False, server_default="running"),
        sa.Column("block_id", sa.Integer(), sa.ForeignKey("training_blocks.id")),
        sa.Column("steps", sa.JSON(), nullable=False, server_default="[]"), sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"), *timestamps(),
    )
    op.create_index("ix_prescribed_workouts_scheduled_date", "prescribed_workouts", ["scheduled_date"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("SELECT create_hypertable('telemetry_records', 'timestamp', if_not_exists => TRUE, migrate_data => TRUE)")


def downgrade() -> None:
    for table in ("prescribed_workouts", "training_blocks", "athlete_invitations", "auth_sessions", "daily_physiology", "telemetry_records", "activities", "users"):
        op.drop_table(table)
    if op.get_bind().dialect.name == "postgresql":
        sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)
