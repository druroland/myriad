"""Authentication router for login/logout/setup."""

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from myriad.core.dependencies import AppSettings, CurrentUserOptional, DbSession
from myriad.core.security import (
    authenticate_user,
    create_session,
    create_user,
    delete_session,
    get_user_count,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def get_templates(settings: AppSettings) -> Jinja2Templates:
    """Get Jinja2 templates instance."""
    return Jinja2Templates(directory=str(settings.templates_dir))


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    settings: AppSettings,
    user: CurrentUserOptional,
    error: str | None = None,
):
    """Display the login page."""
    # If already logged in, redirect to dashboard
    if user:
        return RedirectResponse(url="/", status_code=303)

    templates = get_templates(settings)
    return templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "error": error},
    )


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    username: str = Form(...),
    password: str = Form(...),
):
    """Handle login form submission."""
    user = await authenticate_user(db, username, password)

    if not user:
        templates = get_templates(settings)
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid username or password"},
            status_code=401,
        )

    # Create session
    session = await create_session(
        db,
        user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    # Set cookie and redirect
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="session",
        value=session.id,
        httponly=True,
        samesite="lax",
        max_age=settings.session_expire_hours * 3600,
    )

    return response


@router.get("/logout")
@router.post("/logout")
async def logout(
    request: Request,
    db: DbSession,
):
    """Handle logout."""
    # Get session from request state (set by dependency)
    session = getattr(request.state, "session", None)
    if session:
        await delete_session(db, session.id)

    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie("session")
    return response


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(
    request: Request,
    db: DbSession,
    settings: AppSettings,
    error: str | None = None,
):
    """Display the initial setup page (create first user)."""
    # Check if any users exist
    user_count = await get_user_count(db)
    if user_count > 0:
        return RedirectResponse(url="/auth/login", status_code=303)

    templates = get_templates(settings)
    return templates.TemplateResponse(
        "auth/setup.html",
        {"request": request, "error": error},
    )


@router.post("/setup")
async def setup(
    request: Request,
    db: DbSession,
    settings: AppSettings,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    display_name: str = Form(None),
):
    """Handle initial setup form submission."""
    templates = get_templates(settings)

    # Check if any users exist
    user_count = await get_user_count(db)
    if user_count > 0:
        return RedirectResponse(url="/auth/login", status_code=303)

    # Validate
    if len(username) < 3:
        return templates.TemplateResponse(
            "auth/setup.html",
            {"request": request, "error": "Username must be at least 3 characters"},
            status_code=400,
        )

    if len(password) < 8:
        return templates.TemplateResponse(
            "auth/setup.html",
            {"request": request, "error": "Password must be at least 8 characters"},
            status_code=400,
        )

    if password != password_confirm:
        return templates.TemplateResponse(
            "auth/setup.html",
            {"request": request, "error": "Passwords do not match"},
            status_code=400,
        )

    # Create user
    user = await create_user(db, username, password, display_name or None)

    # Create session
    session = await create_session(
        db,
        user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    # Set cookie and redirect
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="session",
        value=session.id,
        httponly=True,
        samesite="lax",
        max_age=settings.session_expire_hours * 3600,
    )

    return response
