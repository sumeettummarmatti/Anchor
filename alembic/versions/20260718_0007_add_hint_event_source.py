"""add source to hint events"""

import sqlalchemy as sa

from alembic import op

revision = "20260718_0007"
down_revision = "20260717_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hint_events", sa.Column("source", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("hint_events", "source")
