"""Authentication router for login/logout/setup."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from starlette.responses import Response as StarletteResponse

from myriad.core.dependencies import (
    AppSettings,
    CurrentUserOptional,
    DbSession,
    Templates,
)
from myriad.core.security import (
    authenticate_user,
    create_session,
    create_user,
    delete_session,
    get_user_count,
)
from myriad.schemas.auth import SetupRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    templates: Templates,
    user: CurrentUserOptional,
    error: str | None = None,
) -> StarletteResponse:
    """Display the login page."""
    # If already logged in, redirect to dashboard
    if user:
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "error": error},
    )


@router.post("/login")
async def login(
    request: Request,
    db: DbSession,
    settings: AppSettings,
    templates: Templates,
    username: str = Form(...),
    password: str = Form(...),
) -> StarletteResponse:
    """Handle login form submission."""
    user = await authenticate_user(db, username, password)

    if not user:
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
) -> RedirectResponse:
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
    templates: Templates,
    error: str | None = None,
) -> StarletteResponse:
    """Display the initial setup page (create first user)."""
    # Check if any users exist
    user_count = await get_user_count(db)
    if user_count > 0:
        return RedirectResponse(url="/auth/login", status_code=303)

    return templates.TemplateResponse(
        "auth/setup.html",
        {"request": request, "error": error},
    )


@router.post("/setup")
async def setup(
    request: Request,
    db: DbSession,
    settings: AppSettings,
    templates: Templates,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    display_name: str = Form(None),
) -> StarletteResponse:
    """Handle initial setup form submission."""
    # Check if any users exist
    user_count = await get_user_count(db)
    if user_count > 0:
        return RedirectResponse(url="/auth/login", status_code=303)

    # Validate using Pydantic schema
    try:
        setup_data = SetupRequest(
            username=username,
            password=password,
            password_confirm=password_confirm,
            display_name=display_name,
        )
    except ValidationError as e:
        # Extract first error message
        error_msg = e.errors()[0]["msg"]
        return templates.TemplateResponse(
            "auth/setup.html",
            {"request": request, "error": error_msg},
            status_code=400,
        )

    # Create user
    user = await create_user(db, setup_data.username, setup_data.password, setup_data.display_name)

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
