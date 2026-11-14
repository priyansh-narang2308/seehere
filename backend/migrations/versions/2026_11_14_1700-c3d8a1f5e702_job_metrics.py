"""Per-attempt job measurements: run time, CPU, memory, provider calls (Task 33).

Revision ID: c3d8a1f5e702
Revises: b7c2e91d4f30
Create Date: 2026-11-14 17:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d8a1f5e702"
down_revision: str | Sequence[str] | None = "b7c2e91d4f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "job",
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("job", "metrics")
