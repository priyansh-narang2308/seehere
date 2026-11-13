"""The migration creates exactly the modelled schema, and can be rolled back and re-applied."""

from __future__ import annotations

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect

import seehere.db.models  # noqa: F401
from seehere.db.base import Base

EXPECTED_TABLES = {
    "project",
    "media_asset",
    "job",
    "transcript_segment",
    "transcript_word",
    "frame",
    "slide",
    "ocr_region",
    "visual_unit",
    "reference_link",
    "description_cue",
    "evidence",
    "verification_event",
    "schedule_run",
    "schedule_placement",
    "audio_clip",
    "review_decision",
    "export_artifact",
}


def _tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_upgrade_creates_every_modelled_table(migrated_engine: Engine) -> None:
    assert _tables(migrated_engine) == EXPECTED_TABLES
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_migration_matches_models_exactly(migrated_engine: Engine) -> None:
    """No drift: autogenerate against the migrated DB finds nothing to change."""
    with migrated_engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(ctx, Base.metadata)
    assert diff == []


def test_every_foreign_key_is_indexed(migrated_engine: Engine) -> None:
    """Cascading deletes and joins stay fast: each FK column leads some index or unique key."""
    insp = inspect(migrated_engine)
    missing = []
    for table in EXPECTED_TABLES:
        leading = {ix["column_names"][0] for ix in insp.get_indexes(table)}
        leading |= {uq["column_names"][0] for uq in insp.get_unique_constraints(table)}
        for fk in insp.get_foreign_keys(table):
            col = fk["constrained_columns"][0]
            if col not in leading:
                missing.append(f"{table}.{col}")
    assert missing == []


def test_downgrade_to_base_and_back(alembic_cfg: Config, migrated_engine: Engine) -> None:
    cfg = alembic_cfg
    command.downgrade(cfg, "base")
    assert _tables(migrated_engine) == set()
    command.upgrade(cfg, "head")
    assert _tables(migrated_engine) == EXPECTED_TABLES
