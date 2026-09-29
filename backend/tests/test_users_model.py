"""Tests for the User model and Alembic migrations."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from alembic import command
from alembic.config import Config
from app.core.config import get_settings
from app.core.database import Base
from app.models.user import User


@pytest.fixture(scope="session")
def event_loop():
    """Force the test session to use a single event loop."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    """Create an async engine for the test database."""
    _engine = create_async_engine(get_settings().DATABASE_URL)
    yield _engine
    await _engine.dispose()


@pytest.fixture(scope="session")
async def connection(engine):
    """Provide a connection to the test database."""
    async with engine.begin() as conn:
        yield conn


@pytest.fixture(scope="session")
async def setup_database(connection):
    """Set up and tear down the database for migrations tests."""
    await connection.run_sync(Base.metadata.create_all)
    yield
    await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def db_session(engine, connection, setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async session for database interactions within tests."""
    transaction = await connection.begin()
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    async with async_session_maker(bind=connection) as session:
        yield session
    await transaction.rollback()


@pytest.fixture(scope="session")
def alembic_config():
    """Alembic configuration object for tests."""
    alembic_cfg = Config("backend/alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)
    return alembic_cfg


@pytest.mark.asyncio
async def test_alembic_upgrade_downgrade_roundtrip(alembic_config, engine, connection):
    """Test that Alembic migrations can be upgraded and downgraded cleanly."""
    # Ensure database is clean before running migrations
    await connection.run_sync(Base.metadata.drop_all)

    # Upgrade to head
    command.upgrade(alembic_config, "head")

    # Check if 'users' table exists
    async with engine.connect() as conn:
        result = await conn.run_sync(
            lambda sync_conn: sync_conn.execute(
                sa.text("SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = 'users')")
            ).scalar_one()
        )
        assert result is True, "Users table should exist after upgrade"

    # Downgrade by one revision
    command.downgrade(alembic_config, "-1")

    # Check if 'users' table no longer exists
    async with engine.connect() as conn:
        result = await conn.run_sync(
            lambda sync_conn: sync_conn.execute(
                sa.text("SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = 'users')")
            ).scalar_one()
        )
        assert result is False, "Users table should not exist after downgrade"


@pytest.mark.asyncio
async def test_user_model_crud_and_uniqueness(db_session: AsyncSession, engine, alembic_config):
    """Test User model CRUD operations and email uniqueness."""
    # Ensure migrations are up for model tests
    command.upgrade(alembic_config, "head")

    # Test creation and created_at timezone
    email1 = "test@example.com"
    user1 = User(email=email1.lower(), password_hash="hashed_password")
    db_session.add(user1)
    await db_session.commit()
    await db_session.refresh(user1)

    assert user1.id is not None
    assert user1.email == email1.lower()
    assert user1.created_at is not None
    assert user1.created_at.tzinfo is not None
    assert user1.created_at.tzinfo == UTC  # Assuming UTC for func.now()

    # Test case-insensitive uniqueness
    email2 = "Test@example.com"  # Same email, different case
    user2 = User(email=email2, password_hash="another_hash")
    db_session.add(user2)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()

    # Clean up the database by dropping everything after the test completes
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
