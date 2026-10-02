"""DAO for user models."""

from typing import Self
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models.user import User


class UserDAO:
    """Data Access Object for managing user-related operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_user(
        self, email: str, password_hash: str
    ) -> User:
        """Create a new user.

        Args:
            email: The email of the user.
            password_hash: The Argon2id hashed password.

        Returns:
            The newly created User instance.
        """
        user = User(email=email, password_hash=password_hash)
        self.session.add(user)
        await self.session.flush()  # Assigns ID and created_at
        await self.session.refresh(user)
        return user

    async def get_user_by_email(self, email: str) -> User | None:
        """Get a user by their email address.

        Args:
            email: The email address to search for.

        Returns:
            The User instance if found, otherwise None.
        """
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Get a user by their ID.

        Args:
            user_id: The UUID of the user to search for.

        Returns:
            The User instance if found, otherwise None.
        """
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()
