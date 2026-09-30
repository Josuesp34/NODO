"""Encrypted Push subscriptions, durable deliveries and file cleanup registry.

Revision ID: 0008_privacy_push
Revises: 0005_password_reset (root chains parallel migrations on integration)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008_privacy_push"
down_revision = "0005_password_reset"
branch_labels = None
depends_on = None

JSON_VALUE = sa.JSON().with_variant(JSONB(), "postgresql")


def timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade():
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("categories", JSON_VALUE, nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("quiet_start", sa.String(5), nullable=True),
        sa.Column("quiet_end", sa.String(5), nullable=True),
        *timestamps(),
    )
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("subscription_enc", sa.Text(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "subscription_id", sa.Integer(), sa.ForeignKey("push_subscriptions.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("subscription_id", "event_hash", name="uq_push_delivery_event"),
    )
    op.create_index("ix_notification_deliveries_user_id", "notification_deliveries", ["user_id"])
    op.create_index("ix_notification_deliveries_subscription_id", "notification_deliveries", ["subscription_id"])
    op.create_table(
        "privacy_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_kind", sa.String(20), nullable=False),
        sa.Column("locator_enc", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        *timestamps(),
    )
    op.create_index("ix_privacy_artifacts_user_id", "privacy_artifacts", ["user_id"])


def downgrade():
    for table in ("privacy_artifacts", "notification_deliveries", "push_subscriptions", "notification_preferences"):
        op.drop_table(table)
