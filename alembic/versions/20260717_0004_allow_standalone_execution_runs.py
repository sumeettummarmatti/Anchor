"""allow standalone execution runs

Revision ID: 20260717_0004
Revises: 20260717_0003
"""

import sqlalchemy as sa

from alembic import op

revision = "20260717_0004"
down_revision = "20260717_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("execution_runs", "session_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    op.alter_column("execution_runs", "session_id", existing_type=sa.Uuid(), nullable=False)
