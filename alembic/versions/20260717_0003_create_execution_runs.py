"""create execution runs

Revision ID: 20260717_0003
Revises: 20260717_0002
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260717_0003"
down_revision = "20260717_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("code_snapshot", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("stdin", sa.Text(), nullable=False),
        sa.Column("stdout", sa.Text(), nullable=False),
        sa.Column("stderr", sa.Text(), nullable=False),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("static_analysis_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_execution_runs_session_id", "execution_runs", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_execution_runs_session_id", table_name="execution_runs")
    op.drop_table("execution_runs")
