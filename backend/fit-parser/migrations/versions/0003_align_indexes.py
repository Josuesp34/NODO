"""Align model indexes with the persisted PostgreSQL schema.

Revision ID: 0003_align_indexes
Revises: 0002_add_superuser_flag
Create Date: 2026-09-14
"""

from alembic import op


revision = "0003_align_indexes"
down_revision = "0002_add_superuser_flag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_daily_physiology_date_recorded", "daily_physiology", ["date_recorded"])


def downgrade() -> None:
    op.drop_index("ix_daily_physiology_date_recorded", table_name="daily_physiology")
