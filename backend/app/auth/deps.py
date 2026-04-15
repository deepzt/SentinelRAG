from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_token
from app.auth.schemas import UserInToken
from app.auth.service import get_user_by_username
from app.core.database import get_db
from app.models.user import User

_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency — validates JWT and returns the live User ORM object.

    Validates:
    1. Bearer token is present
    2. JWT signature + expiry (jose raises JWTError on failure)
    3. 'sub' claim resolves to an existing user in the DB
    """
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims: UserInToken = decode_token(credentials.credentials)
    except JWTError:
        raise exc

    user = await get_user_by_username(db, claims.sub)
    if user is None:
        raise exc

    return user
