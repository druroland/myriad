"""FastAPI application factory and CLI entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from myriad.config import init_settings
from myriad.core.database import close_db, get_session_context, init_db
from myriad.core.security import get_user_count
from myriad.routers import auth_router, dashboard_router, hosts_router
from myriad.services import LocationService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Myriad...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Ensure locations from config exist in DB
    settings = app.state.settings
    async with get_session_context() as db:
        location_service = LocationService(db)
        for loc in settings.locations:
            await location_service.ensure_from_config(loc.id, loc.name, loc.network_cidr)
        logger.info(f"Ensured {len(settings.locations)} locations from config")

    yield

    # Cleanup
    await close_db()
    logger.info("Myriad shutdown complete")


def create_app(config_dir: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config_dir: Path to configuration directory

    Returns:
        Configured FastAPI application
    """
    # Initialize settings
    settings = init_settings(config_dir)

    # Create app
    app = FastAPI(
        title="Myriad",
        description="Home Infrastructure Management System",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Store settings in app state
    app.state.settings = settings

    # Mount static files
    static_path = settings.static_dir
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    # Include routers
    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(hosts_router)

    # Middleware to check for setup
    @app.middleware("http")
    async def check_setup_middleware(request: Request, call_next):
        """Redirect to setup if no users exist."""
        # Skip for static files and auth routes
        path = request.url.path
        if path.startswith("/static") or path.startswith("/auth") or path == "/check-setup":
            return await call_next(request)

        # Check if any users exist
        async with get_session_context() as db:
            user_count = await get_user_count(db)

        if user_count == 0:
            return RedirectResponse(url="/auth/setup", status_code=303)

        return await call_next(request)

    return app


def cli():
    """CLI entry point for running the server."""
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Myriad - Home Infrastructure Management")
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=Path("config"),
        help="Path to configuration directory",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    # Create app with config
    app = create_app(args.config)

    # Override settings from CLI
    if args.debug:
        app.state.settings.server.debug = True

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


# Create default app instance for uvicorn
app = create_app()

if __name__ == "__main__":
    cli()
