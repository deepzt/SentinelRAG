from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.password import verify_password
from app.models.user import User


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> User | None:
    """Return the User if credentials are valid, None otherwise.

    Performs a constant-time password check via bcrypt to resist timing attacks.
    """
    user = await get_user_by_username(db, username)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
