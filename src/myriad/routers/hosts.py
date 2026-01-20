"""Hosts router for managing discovered hosts."""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from starlette.responses import Response

from myriad.core.dependencies import (
    AuthenticatedUser,
    HostServiceDep,
    LocationServiceDep,
    SyncServiceDep,
    Templates,
)
from myriad.models import HostStatus
from myriad.schemas import HostCreate, HostResponse, HostSyncResult, HostUpdate

router = APIRouter(prefix="/hosts", tags=["hosts"])


@router.get("", response_class=HTMLResponse)
async def hosts_page(
    request: Request,
    user: AuthenticatedUser,
    templates: Templates,
    host_service: HostServiceDep,
    location_service: LocationServiceDep,
    location: str | None = None,
    status: HostStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=100),
) -> Response:
    """Display the hosts list page."""
    offset = (page - 1) * page_size
    hosts, total = await host_service.get_all(
        location_id=location,
        status=status,
        limit=page_size,
        offset=offset,
    )

    locations = await location_service.get_all()
    total_pages = (total + page_size - 1) // page_size

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
    user: AuthenticatedUser,
    templates: Templates,
    host_service: HostServiceDep,
    location: str | None = None,
    status: HostStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=100),
) -> Response:
    """Get just the hosts table (for HTMX partial updates)."""
    offset = (page - 1) * page_size
    hosts, total = await host_service.get_all(
        location_id=location,
        status=status,
        limit=page_size,
        offset=offset,
    )

    total_pages = (total + page_size - 1) // page_size

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
    user: AuthenticatedUser,
    templates: Templates,
    host_service: HostServiceDep,
) -> Response:
    """Display host detail page."""
    host = await host_service.get_by_id(host_id)

    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

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
    user: AuthenticatedUser,
    templates: Templates,
    host_service: HostServiceDep,
) -> Response:
    """Handle host edit form submission."""
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
    user: AuthenticatedUser,
    sync_service: SyncServiceDep,
) -> HostSyncResult:
    """Trigger a host sync from an OPNsense integration."""
    try:
        result = await sync_service.sync_opnsense(integration_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/sync")
async def sync_all_hosts(
    user: AuthenticatedUser,
    sync_service: SyncServiceDep,
) -> list[HostSyncResult]:
    """Trigger a sync from all configured integrations."""
    results = await sync_service.sync_all_opnsense()
    return results


@router.get("/api/{host_id}", response_model=HostResponse)
async def get_host_api(
    host_id: int,
    user: AuthenticatedUser,
    host_service: HostServiceDep,
) -> HostResponse:
    """Get host by ID (JSON API)."""
    host = await host_service.get_by_id(host_id)

    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    return HostResponse.model_validate(host)


@router.post("/api", response_model=HostResponse)
async def create_host_api(
    data: HostCreate,
    user: AuthenticatedUser,
    host_service: HostServiceDep,
) -> HostResponse:
    """Create a new host (JSON API)."""
    # Check for duplicate MAC
    existing = await host_service.get_by_mac(data.mac_address)
    if existing:
        raise HTTPException(status_code=409, detail="Host with this MAC address already exists")

    host = await host_service.create(data)
    return HostResponse.model_validate(host)


@router.delete("/api/{host_id}")
async def delete_host_api(
    host_id: int,
    user: AuthenticatedUser,
    host_service: HostServiceDep,
) -> dict[str, str | int]:
    """Delete a host (JSON API)."""
    host = await host_service.get_by_id(host_id)

    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    await host_service.delete(host)
    return {"status": "deleted", "id": host_id}
