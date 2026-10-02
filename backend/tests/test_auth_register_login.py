"""Tests for email+password registration and login (DrawLift #91).

Uses an isolated in-memory SQLite database by overriding the ``get_db``
dependency, so no live PostgreSQL is required.
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.auth.hashing import verify_password
from app.core.database import get_db
from app.main import app
from app.models.user import User  # noqa: F401  (register model on Base)


@pytest.fixture
async def isolated_db() -> (
    AsyncGenerator[tuple[AsyncClient, async_sessionmaker[AsyncSession]], None]
):
    """Async client + session maker backed by isolated in-memory SQLite."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(User.__table__.create)
        # Mirror migration 0003's unique lower(email) index so duplicate
        # detection behaves like production PostgreSQL.
        await conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower" " ON users (lower(email))"
        )
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, session_maker
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


@pytest.mark.asyncio
async def test_register_login_round_trip(isolated_db):
    """Register -> login round-trip returns 200 and never echoes secrets."""
    client, _ = isolated_db
    email = _email("user")
    password = "correct-horse-9"

    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert reg.status_code == 201, reg.text
    body = reg.json()
    assert body["email"] == email
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body
    assert "$argon2" not in reg.text

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    assert login.json()["email"] == email


@pytest.mark.asyncio
async def test_duplicate_registration_returns_409(isolated_db):
    """Second registration with the same email returns stable 409."""
    client, _ = isolated_db
    payload = {"email": _email("dup"), "password": "another-pass-1"}

    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201, first.text

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["detail"] == "Email already registered"


@pytest.mark.asyncio
async def test_register_validation_returns_422(isolated_db):
    """Short password and malformed email are rejected with 422."""
    client, _ = isolated_db
    short = await client.post(
        "/api/v1/auth/register",
        json={"email": "valid@example.com", "password": "short"},
    )
    assert short.status_code == 422

    bad_email = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "valid-pass-1"},
    )
    assert bad_email.status_code == 422


@pytest.mark.asyncio
async def test_login_rejects_wrong_and_unknown_with_401(isolated_db):
    """Wrong password and unknown email both return identical 401."""
    client, _ = isolated_db
    email = _email("login")
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "valid-pass-1"},
    )
    assert reg.status_code == 201, reg.text

    wrong = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "wrong-pass-2"},
    )
    assert wrong.status_code == 401

    unknown = await client.post(
        "/api/v1/auth/login",
        json={"email": _email("ghost"), "password": "valid-pass-1"},
    )
    assert unknown.status_code == 401
    # No user-enumeration signal: identical status and message.
    assert wrong.status_code == unknown.status_code
    assert wrong.json() == unknown.json()


@pytest.mark.asyncio
async def test_password_stored_as_argon2id_hash(isolated_db):
    """Persisted hash starts with $argon2id$ and differs from plaintext."""
    client, session_maker = isolated_db
    email = _email("hash")
    password = "plaintext-pass-1"
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 201, reg.text

    async with session_maker() as session:
        result = await session.execute(select(User).where(User.email == email))
        stored = result.scalars().one()

    assert stored.password_hash.startswith("$argon2id$")
    assert stored.password_hash != password
    assert "bcrypt" not in stored.password_hash
    assert verify_password(stored.password_hash, password) is True
    assert verify_password(stored.password_hash, "other-password-1") is False
