"""Add one-time password recovery tokens.

Revision ID: 0005_password_reset
Revises: 0004_pilot_backend
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_password_reset"
down_revision = "0004_pilot_backend"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "prescribed_workouts",
            "steps",
            existing_type=sa.JSON(),
            type_=JSONB(),
            postgresql_using="steps::jsonb",
        )
    op.create_table(
        "password_resets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_password_resets_user_id", "password_resets", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_password_resets_user_id", table_name="password_resets")
    op.drop_table("password_resets")
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "prescribed_workouts",
            "steps",
            existing_type=JSONB(),
            type_=sa.JSON(),
            postgresql_using="steps::json",
        )
