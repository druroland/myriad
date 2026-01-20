"""Dashboard router for the main overview page."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from myriad.core.dependencies import AppSettings, AuthenticatedUser, DbSession
from myriad.core.security import get_user_count
from myriad.services import HostService

router = APIRouter(tags=["dashboard"])


def get_templates(settings: AppSettings) -> Jinja2Templates:
    """Get Jinja2 templates instance."""
    return Jinja2Templates(directory=str(settings.templates_dir))


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: DbSession,
    settings: AppSettings,
    user: AuthenticatedUser,
):
    """Display the main dashboard."""
    host_service = HostService(db)
    stats = await host_service.get_stats()

    templates = get_templates(settings)
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
async def check_setup(db: DbSession):
    """Check if initial setup is needed."""
    user_count = await get_user_count(db)
    if user_count == 0:
        return RedirectResponse(url="/auth/setup", status_code=303)
    return RedirectResponse(url="/auth/login", status_code=303)
