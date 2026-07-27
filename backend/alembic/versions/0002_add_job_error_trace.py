"""add job error trace

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-27 21:40:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("error_trace", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "error_trace")
