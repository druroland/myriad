"""Security utilities for password hashing and session management."""

import secrets
from datetime import datetime, timedelta

from passlib.context import CryptContext
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from myriad.config import get_settings
from myriad.models import Session, User

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def generate_session_id() -> str:
    """Generate a secure random session ID."""
    return secrets.token_hex(32)


async def create_session(
    db: AsyncSession,
    user: User,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Session:
    """Create a new session for a user."""
    settings = get_settings()

    session = Session(
        id=generate_session_id(),
        user_id=user.id,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=settings.session_expire_hours),
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.add(session)
    await db.flush()

    return session


async def get_session(db: AsyncSession, session_id: str) -> Session | None:
    """Get a session by ID, returning None if expired or not found."""
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.expires_at > datetime.utcnow(),
        )
    )
    return result.scalar_one_or_none()


async def get_session_with_user(db: AsyncSession, session_id: str) -> tuple[Session, User] | None:
    """Get a session and its associated user."""
    result = await db.execute(
        select(Session, User)
        .join(User)
        .where(
            Session.id == session_id,
            Session.expires_at > datetime.utcnow(),
            User.is_active == True,  # noqa: E712
        )
    )
    row = result.first()
    if row:
        return row.tuple()
    return None


async def delete_session(db: AsyncSession, session_id: str) -> bool:
    """Delete a session."""
    result = await db.execute(delete(Session).where(Session.id == session_id))
    return result.rowcount > 0


async def delete_user_sessions(db: AsyncSession, user_id: int) -> int:
    """Delete all sessions for a user."""
    result = await db.execute(delete(Session).where(Session.user_id == user_id))
    return result.rowcount


async def cleanup_expired_sessions(db: AsyncSession) -> int:
    """Remove all expired sessions."""
    result = await db.execute(delete(Session).where(Session.expires_at <= datetime.utcnow()))
    return result.rowcount


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    """Authenticate a user by username and password."""
    result = await db.execute(
        select(User).where(User.username == username, User.is_active == True)  # noqa: E712
    )
    user = result.scalar_one_or_none()

    if user and verify_password(password, user.password_hash):
        # Update last login
        user.last_login = datetime.utcnow()
        return user

    return None


async def create_user(
    db: AsyncSession,
    username: str,
    password: str,
    display_name: str | None = None,
) -> User:
    """Create a new user."""
    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    await db.flush()
    return user


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """Get a user by username."""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_count(db: AsyncSession) -> int:
    """Get the total number of users."""
    from sqlalchemy import func

    result = await db.execute(select(func.count(User.id)))
    return result.scalar_one()
