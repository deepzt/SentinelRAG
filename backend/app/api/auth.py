from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.schemas import LoginRequest, TokenResponse, UserInToken, UserResponse
from app.auth.service import authenticate_user
from app.auth.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate and return a JWT.

    Returns a generic error on failure to prevent username enumeration.
    """
    user = await authenticate_user(db, body.username, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = UserInToken(
        sub=user.username,
        user_id=str(user.id),
        role=user.role,
        department=user.department,
    )
    token = create_access_token(claims)

    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the authenticated user's profile."""
    return UserResponse.model_validate(current_user)
