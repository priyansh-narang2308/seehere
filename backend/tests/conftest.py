"""Shared fixtures. Database tests run against a throwaway `seehere_test` database on the same
Postgres server as DATABASE_URL (start it with `make db-up`). Dev data is never touched."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine, make_url, text
from sqlalchemy.orm import Session, sessionmaker

from seehere.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent
TEST_DB_NAME = "seehere_test"


def _test_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    url = make_url(get_settings().database_url).set(database=TEST_DB_NAME)
    return url.render_as_string(hide_password=False)


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


@pytest.fixture(scope="session")
def test_db_url() -> Iterator[str]:
    """Create a fresh, empty test database for the session and drop it afterwards."""
    url = _test_url()
    db_name = make_url(url).database
    assert db_name and db_name.endswith("_test"), "refusing to use a non-test database"
    admin_url = make_url(url).set(database="postgres")
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    except Exception as exc:  # pragma: no cover - environment problem, explained below
        pytest.fail(
            f"Postgres is not reachable for tests ({type(exc).__name__}). Run `make db-up`."
        )
    yield url
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(scope="session")
def alembic_cfg(test_db_url: str) -> Config:
    return alembic_config(test_db_url)


@pytest.fixture(scope="session")
def migrated_engine(test_db_url: str, alembic_cfg: Config) -> Iterator[Engine]:
    """Test database upgraded to the latest migration."""
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(test_db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(migrated_engine: Engine) -> Iterator[Session]:
    """A session inside a transaction that is rolled back after each test."""
    connection: Connection = migrated_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def sessions(migrated_engine: Engine) -> Iterator[sessionmaker[Session]]:
    """Real, committing sessions (separate connections), for tests where several workers or
    processes must see each other's committed rows. All data is truncated afterwards."""
    factory = sessionmaker(bind=migrated_engine, expire_on_commit=False)
    yield factory
    with migrated_engine.begin() as conn:
        conn.execute(text("TRUNCATE project CASCADE"))
