"""Add the application-level superuser capability.

Revision ID: 0002_add_superuser_flag
Revises: 0001_nodo_core
Create Date: 2026-09-13
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_add_superuser_flag"
down_revision = "0001_nodo_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "is_superuser")
