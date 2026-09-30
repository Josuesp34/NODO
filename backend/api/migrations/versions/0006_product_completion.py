"""CAS for manual product flows and traceable template application.

Revision ID: 0006_product_completion
Revises: 0005_password_reset

0004 creates product tables from live metadata, so both fresh and existing
installations must be supported without re-adding columns or constraints.
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_product_completion"
down_revision = "0005_password_reset"
branch_labels = None
depends_on = None


def upgrade():
    for table in ["activities", "complaints", "review_items", "competitions", "group_memberships"]:
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE plan_assignments ADD COLUMN IF NOT EXISTS workout_refs JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint
                           WHERE conname = 'uq_decision_recommendation' AND conrelid = 'decisions'::regclass) THEN
                ALTER TABLE decisions ADD CONSTRAINT uq_decision_recommendation UNIQUE (recommendation_id);
            END IF;
        END $$
    """)
    op.alter_column("activities", "total_distance_m", existing_type=sa.Float(), nullable=True, server_default=None)
    # Historical zero was the ingestion default, not a measured distance.
    op.execute("UPDATE activities SET total_distance_m = NULL WHERE total_distance_m = 0")


def downgrade():
    op.drop_constraint("uq_decision_recommendation", "decisions", type_="unique")
    op.drop_column("plan_assignments", "workout_refs")
    for table in ["group_memberships", "competitions", "review_items", "complaints", "activities"]:
        op.drop_column(table, "version")
    op.execute("UPDATE activities SET total_distance_m = 0 WHERE total_distance_m IS NULL")
    op.alter_column("activities", "total_distance_m", existing_type=sa.Float(), nullable=False, server_default="0")
