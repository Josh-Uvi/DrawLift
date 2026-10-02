"""Auth API endpoints: POST /auth/register, POST /auth/login."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.hashing import hash_password, verify_password
from app.auth.schemas import LoginRequest, RegisterRequest, UserPublic
from app.core.database import get_db
from app.models.user import User

router = APIRouter()

_INVALID_CREDENTIALS_DETAIL = "Invalid email or password"


def _normalize_email(email: str) -> str:
    """Lowercase and strip the email for case-insensitive uniqueness."""
    return email.strip().lower()


@router.post(
    "/auth/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserPublic:
    """Register a new user with email + Argon2id-hashed password.

    Returns 201 with the public user (never the password/hash).
    Returns 409 when the email is already registered. The duplicate is
    detected by catching IntegrityError (not a pre-check SELECT) so
    concurrent registrations cannot race.
    """
    user = User(
        id=uuid.uuid4(),
        email=_normalize_email(str(payload.email)),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc
    await db.refresh(user)
    return UserPublic(id=user.id, email=user.email, created_at=user.created_at)


@router.post("/auth/login", response_model=UserPublic)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> UserPublic:
    """Authenticate with email + password.

    Returns 200 with the public user for valid credentials. Returns 401
    with an identical message for both unknown email and wrong password,
    so callers cannot enumerate registered emails.
    """
    result = await db.execute(
        select(User).where(User.email == _normalize_email(str(payload.email)))
    )
    user = result.scalars().first()
    if user is None or not verify_password(user.password_hash, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDENTIALS_DETAIL,
        )
    return UserPublic(id=user.id, email=user.email, created_at=user.created_at)
