"""Pydantic schemas for email+password registration and login."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Registration payload: email + password (min 8 chars)."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Login payload: same shape as registration."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserPublic(BaseModel):
    """Public user representation: never includes password or hash."""

    id: UUID
    email: str
    created_at: datetime
