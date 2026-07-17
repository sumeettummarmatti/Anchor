"""create hint events

Revision ID: 20260717_0005
Revises: 20260717_0004
"""

import sqlalchemy as sa

from alembic import op

revision = "20260717_0005"
down_revision = "20260717_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hint_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hint_events_user_id", "hint_events", ["user_id"])
    op.create_index("ix_hint_events_session_id", "hint_events", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_hint_events_session_id", table_name="hint_events")
    op.drop_index("ix_hint_events_user_id", table_name="hint_events")
    op.drop_table("hint_events")
