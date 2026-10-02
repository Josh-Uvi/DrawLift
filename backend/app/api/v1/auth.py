"""API v1 authentication routes."""

from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from backend.app.auth.hashing import hash_password, verify_password
from backend.app.auth.schemas import LoginRequest, RegisterRequest, UserPublic
from backend.app.db.dao.user import UserDAO

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    name="auth:register",
)
async def register(
    user_data: RegisterRequest,
    user_dao: UserDAO,
) -> UserPublic:
    """Register a new user with email and password."""
    try:
        user = await user_dao.create_user(
            email=user_data.email,
            password_hash=hash_password(user_data.password),
        )
        return user
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors(),
        )


@router.post(
    "/login",
    response_model=UserPublic,
    status_code=status.HTTP_200_OK,
    name="auth:login",
)
async def login(
    user_data: LoginRequest,
    user_dao: UserDAO,
) -> UserPublic:
    """Authenticate a user with email and password."""
    user = await user_dao.get_user_by_email(email=user_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not verify_password(user.password_hash, user_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return user
