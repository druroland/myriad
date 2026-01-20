"""FastAPI dependencies for authentication and common resources."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from myriad.config import Settings, get_settings
from myriad.core.database import get_session
from myriad.core.security import get_session_with_user
from myriad.core.templates import get_templates
from myriad.models import User
from myriad.services import HostService, LocationService, SyncService

# Type aliases for dependency injection
DbSession = Annotated[AsyncSession, Depends(get_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


# Template dependency
def get_jinja_templates(settings: AppSettings) -> Jinja2Templates:
    """Get Jinja2 templates instance from settings."""
    return get_templates(str(settings.templates_dir))


Templates = Annotated[Jinja2Templates, Depends(get_jinja_templates)]


# Service dependencies
def get_host_service(db: DbSession) -> HostService:
    """Get HostService instance."""
    return HostService(db)


def get_location_service(db: DbSession) -> LocationService:
    """Get LocationService instance."""
    return LocationService(db)


def get_sync_service(db: DbSession, settings: AppSettings) -> SyncService:
    """Get SyncService instance."""
    return SyncService(db, settings)


HostServiceDep = Annotated[HostService, Depends(get_host_service)]
LocationServiceDep = Annotated[LocationService, Depends(get_location_service)]
SyncServiceDep = Annotated[SyncService, Depends(get_sync_service)]


async def get_current_user_optional(
    request: Request,
    db: DbSession,
    session_id: Annotated[str | None, Cookie(alias="session")] = None,
) -> User | None:
    """Get the current user if authenticated, None otherwise."""
    if not session_id:
        return None

    result = await get_session_with_user(db, session_id)
    if result:
        session, user = result
        # Store session in request state for potential logout
        request.state.session = session
        return user

    return None


async def get_current_user(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User:
    """Get the current authenticated user, raising 401 if not authenticated."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


# Type aliases for authenticated dependencies
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserOptional = Annotated[User | None, Depends(get_current_user_optional)]


def require_auth_redirect(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User:
    """Require authentication, redirect to login if not authenticated.

    For use with HTML endpoints that should redirect to login page.
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/auth/login"},
        )
    return user


AuthenticatedUser = Annotated[User, Depends(require_auth_redirect)]


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Alias for get_session for explicit naming."""
    async for session in get_session():
        yield session
