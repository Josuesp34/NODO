"""OAuth state, provider evidence and aggregate assistant accounting."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007_providers_assistant"
down_revision = "0006_product_completion"
branch_labels = None
depends_on = None


def upgrade():
    json_type = sa.JSON().with_variant(JSONB(), "postgresql")
    op.create_table(
        "provider_oauth_states",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("auth_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("state_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_provider_oauth_states_athlete_id", "provider_oauth_states", ["athlete_id"])
    op.create_index("ix_provider_oauth_states_user_id", "provider_oauth_states", ["user_id"])
    op.create_table(
        "provider_records",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("athlete_id", "provider", "kind", "external_id", name="uq_provider_record"),
    )
    op.create_index("ix_provider_records_athlete_id", "provider_records", ["athlete_id"])
    op.create_table(
        "assistant_runs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("assistant_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_key", sa.String(80), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("result", json_type, nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_microusd", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("thread_id", "request_key", name="uq_assistant_run_request"),
    )
    op.create_index("ix_assistant_runs_thread_id", "assistant_runs", ["thread_id"])
    op.create_index("ix_assistant_runs_user_id", "assistant_runs", ["user_id"])
    op.create_table(
        "assistant_budgets",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_microusd", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("scope", "scope_id", "month", name="uq_assistant_budget_month"),
    )

    condition = sa.text("status IN ('connected', 'syncing', 'disconnect_pending') AND external_athlete_id IS NOT NULL")
    # 0004 uses the registered pilot-table metadata on a fresh install.
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("athlete_connections")}
    if "uq_active_intervals_external" not in indexes:
        op.create_index(
            "uq_active_intervals_external",
            "athlete_connections",
            ["provider", "external_athlete_id"],
            unique=True,
            postgresql_where=condition,
            sqlite_where=condition,
        )


def downgrade():
    op.drop_index("uq_active_intervals_external", table_name="athlete_connections")
    op.drop_table("assistant_budgets")
    op.drop_table("assistant_runs")
    op.drop_table("provider_records")
    op.drop_table("provider_oauth_states")
