"""Dashboard router for the main overview page."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import Response

from myriad.core.dependencies import (
    AppSettings,
    AuthenticatedUser,
    DbSession,
    HostServiceDep,
    Templates,
)
from myriad.core.security import get_user_count

router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    settings: AppSettings,
    user: AuthenticatedUser,
    templates: Templates,
    host_service: HostServiceDep,
) -> Response:
    """Display the main dashboard."""
    stats = await host_service.get_stats()

    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "user": user,
            "stats": stats,
            "locations": settings.locations,
            "integrations": {
                "opnsense": len(settings.integrations.opnsense),
                "unifi": len(settings.integrations.unifi),
            },
        },
    )


@router.get("/check-setup")
async def check_setup(db: DbSession) -> RedirectResponse:
    """Check if initial setup is needed."""
    user_count = await get_user_count(db)
    if user_count == 0:
        return RedirectResponse(url="/auth/setup", status_code=303)
    return RedirectResponse(url="/auth/login", status_code=303)
