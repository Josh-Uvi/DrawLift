"""create jobs table

Revision ID: 0001
Revises:
Create Date: 2025-07-23 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("step", sa.String(50), nullable=True),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("input_file", sa.String(500), nullable=False),
        sa.Column("output_file", sa.String(500), nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("error_msg", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_jobs_created_at", "jobs", [sa.text("created_at DESC")])
    op.create_index("idx_jobs_status", "jobs", ["status"])


def downgrade() -> None:
    op.drop_index("idx_jobs_status", table_name="jobs")
    op.drop_index("idx_jobs_created_at", table_name="jobs")
    op.drop_table("jobs")
