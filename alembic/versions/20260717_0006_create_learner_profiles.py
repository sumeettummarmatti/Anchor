"""create learner profiles

Revision ID: 20260717_0006
Revises: 20260717_0005
"""

import sqlalchemy as sa

from alembic import op

revision = "20260717_0006"
down_revision = "20260717_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learner_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("hint_depth_ceiling", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("teaching_style", sa.String(length=32), nullable=False, server_default="socratic"),
        sa.Column("difficulty_adjustment", sa.Float(), nullable=False, server_default="0"),
        sa.Column("intervention_frequency", sa.Float(), nullable=False, server_default="0.35"),
        sa.Column("rolling_hint_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rolling_failed_run_ratio", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rolling_avg_solve_time_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sessions_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("execution_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hints_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_learner_profiles_user_id", "learner_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_learner_profiles_user_id", table_name="learner_profiles")
    op.drop_table("learner_profiles")
