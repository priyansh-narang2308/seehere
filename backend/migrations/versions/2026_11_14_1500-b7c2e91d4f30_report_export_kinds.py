"""Coverage and verification report export kinds (Task 28).

Revision ID: b7c2e91d4f30
Revises: a4fb4ab3d850
Create Date: 2026-11-14 15:00:00

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b7c2e91d4f30"
down_revision: str | Sequence[str] | None = "a4fb4ab3d850"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BEFORE = [
    "webvtt",
    "cue_audio_zip",
    "standard_mp4",
    "extended_mp4",
    "transcript_html",
    "manifest_json",
    "bundle_zip",
]
AFTER = [*BEFORE, "report_html", "report_json"]


def _check(kinds: list[str]) -> None:
    op.drop_constraint(op.f("ck_export_artifact_export_kind"), "export_artifact", type_="check")
    allowed = ", ".join(f"'{k}'" for k in kinds)
    op.create_check_constraint("export_kind", "export_artifact", f"kind IN ({allowed})")


def upgrade() -> None:
    _check(AFTER)


def downgrade() -> None:
    op.execute("DELETE FROM export_artifact WHERE kind IN ('report_html', 'report_json')")
    _check(BEFORE)
