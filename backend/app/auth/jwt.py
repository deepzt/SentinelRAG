from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.auth.schemas import UserInToken
from app.core.config import settings


def create_access_token(user_claims: UserInToken) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        **user_claims.model_dump(),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> UserInToken:
    """Decode and validate a JWT.

    Raises jose.JWTError on invalid signature, expiry, or malformed token.
    The 'alg: none' attack is mitigated because we explicitly pass
    algorithms=[settings.JWT_ALGORITHM] — jose rejects any other algorithm.
    """
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],  # explicit list blocks alg:none
    )
    return UserInToken(
        sub=payload["sub"],
        user_id=payload["user_id"],
        role=payload["role"],
        department=payload["department"],
    )
