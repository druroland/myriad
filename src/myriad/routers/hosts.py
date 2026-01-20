"""Hosts router for managing discovered hosts."""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from myriad.core.dependencies import AppSettings, AuthenticatedUser, DbSession
from myriad.models import HostStatus
from myriad.schemas import HostCreate, HostResponse, HostSyncResult, HostUpdate
from myriad.services import HostService, LocationService, SyncService

router = APIRouter(prefix="/hosts", tags=["hosts"])


def get_templates(settings: AppSettings) -> Jinja2Templates:
    """Get Jinja2 templates instance."""
    return Jinja2Templates(directory=str(settings.templates_dir))


@router.get("", response_class=HTMLResponse)
async def hosts_page(
    request: Request,
    db: DbSession,
    settings: AppSettings,
    user: AuthenticatedUser,
    location: str | None = None,
    status: HostStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=100),
):
    """Display the hosts list page."""
    host_service = HostService(db)
    location_service = LocationService(db)

    offset = (page - 1) * page_size
    hosts, total = await host_service.get_all(
        location_id=location,
        status=status,
        limit=page_size,
        offset=offset,
    )

    locations = await location_service.get_all()
    total_pages = (total + page_size - 1) // page_size

    templates = get_templates(settings)
    return templates.TemplateResponse(
        "hosts/list.html",
        {
            "request": request,
            "user": user,
            "hosts": hosts,
            "locations": locations,
            "current_location": location,
            "current_status": status,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
    )


@router.get("/table", response_class=HTMLResponse)
async def hosts_table(
    request: Request,
    db: DbSession,
    settings: AppSettings,
    user: AuthenticatedUser,
    location: str | None = None,
    status: HostStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=100),
):
    """Get just the hosts table (for HTMX partial updates)."""
    host_service = HostService(db)

    offset = (page - 1) * page_size
    hosts, total = await host_service.get_all(
        location_id=location,
        status=status,
        limit=page_size,
        offset=offset,
    )

    total_pages = (total + page_size - 1) // page_size

    templates = get_templates(settings)
    return templates.TemplateResponse(
        "hosts/_table.html",
        {
            "request": request,
            "hosts": hosts,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
    )


@router.get("/{host_id}", response_class=HTMLResponse)
async def host_detail(
    request: Request,
    host_id: int,
    db: DbSession,
    settings: AppSettings,
    user: AuthenticatedUser,
):
    """Display host detail page."""
    host_service = HostService(db)
    host = await host_service.get_by_id(host_id)

    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    templates = get_templates(settings)
    return templates.TemplateResponse(
        "hosts/detail.html",
        {
            "request": request,
            "user": user,
            "host": host,
        },
    )


@router.post("/{host_id}/edit", response_class=HTMLResponse)
async def host_edit(
    request: Request,
    host_id: int,
    db: DbSession,
    settings: AppSettings,
    user: AuthenticatedUser,
):
    """Handle host edit form submission."""
    host_service = HostService(db)
    host = await host_service.get_by_id(host_id)

    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    form_data = await request.form()

    update_data = HostUpdate(
        display_name=form_data.get("display_name") or None,
        host_type=form_data.get("host_type") or None,
        location_id=form_data.get("location_id") or None,
        notes=form_data.get("notes") or None,
    )

    host = await host_service.update(host, update_data)

    templates = get_templates(settings)
    return templates.TemplateResponse(
        "hosts/_detail_card.html",
        {
            "request": request,
            "host": host,
        },
    )


# API endpoints for HTMX/JSON

@router.post("/sync/{integration_id}")
async def sync_hosts(
    integration_id: str,
    db: DbSession,
    settings: AppSettings,
    user: AuthenticatedUser,
) -> HostSyncResult:
    """Trigger a host sync from an OPNsense integration."""
    sync_service = SyncService(db, settings)

    try:
        result = await sync_service.sync_opnsense(integration_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/sync")
async def sync_all_hosts(
    db: DbSession,
    settings: AppSettings,
    user: AuthenticatedUser,
) -> list[HostSyncResult]:
    """Trigger a sync from all configured integrations."""
    sync_service = SyncService(db, settings)
    results = await sync_service.sync_all_opnsense()
    return results


@router.get("/api/{host_id}", response_model=HostResponse)
async def get_host_api(
    host_id: int,
    db: DbSession,
    user: AuthenticatedUser,
) -> HostResponse:
    """Get host by ID (JSON API)."""
    host_service = HostService(db)
    host = await host_service.get_by_id(host_id)

    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    return HostResponse.model_validate(host)


@router.post("/api", response_model=HostResponse)
async def create_host_api(
    data: HostCreate,
    db: DbSession,
    user: AuthenticatedUser,
) -> HostResponse:
    """Create a new host (JSON API)."""
    host_service = HostService(db)

    # Check for duplicate MAC
    existing = await host_service.get_by_mac(data.mac_address)
    if existing:
        raise HTTPException(status_code=409, detail="Host with this MAC address already exists")

    host = await host_service.create(data)
    return HostResponse.model_validate(host)


@router.delete("/api/{host_id}")
async def delete_host_api(
    host_id: int,
    db: DbSession,
    user: AuthenticatedUser,
):
    """Delete a host (JSON API)."""
    host_service = HostService(db)
    host = await host_service.get_by_id(host_id)

    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    await host_service.delete(host)
    return {"status": "deleted", "id": host_id}
