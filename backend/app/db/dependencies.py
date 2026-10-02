"""Dependency injection for database session and DAOs."""

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.dao.user import UserDAO
from backend.app.core.database import async_session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields an async session for database operations."""
    async with async_session() as session:
        yield session


def get_user_dao(session: AsyncSession = Depends(get_session)) -> UserDAO:
    """Returns a UserDAO instance with an injected session."""
    return UserDAO(session)
