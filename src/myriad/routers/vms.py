"""VMs router for managing virtual machines."""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from starlette.responses import Response

from myriad.core.dependencies import AuthenticatedUser, ProxmoxServiceDep, Templates
from myriad.models import VMState, VMType
from myriad.schemas.vm import (
    HypervisorResponse,
    VMDetailResponse,
    VMSnapshotResponse,
    VMStatsResponse,
    VMSyncResult,
)

router = APIRouter(prefix="/vms", tags=["vms"])


@router.get("", response_class=HTMLResponse)
async def vms_page(
    request: Request,
    user: AuthenticatedUser,
    templates: Templates,
    proxmox_service: ProxmoxServiceDep,
    hypervisor: str | None = None,
    state: VMState | None = None,
    vm_type: VMType | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=100),
) -> Response:
    """Display the VMs list page."""
    offset = (page - 1) * page_size
    vms, total = await proxmox_service.get_all_vms(
        hypervisor_id=hypervisor,
        state=state,
        vm_type=vm_type,
        limit=page_size,
        offset=offset,
    )

    hypervisors = await proxmox_service.get_hypervisors()
    stats = await proxmox_service.get_vm_stats()
    total_pages = (total + page_size - 1) // page_size

    return templates.TemplateResponse(
        "vms/list.html",
        {
            "request": request,
            "user": user,
            "vms": vms,
            "hypervisors": hypervisors,
            "stats": stats,
            "current_hypervisor": hypervisor,
            "current_state": state,
            "current_vm_type": vm_type,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
    )


@router.get("/table", response_class=HTMLResponse)
async def vms_table(
    request: Request,
    user: AuthenticatedUser,
    templates: Templates,
    proxmox_service: ProxmoxServiceDep,
    hypervisor: str | None = None,
    state: VMState | None = None,
    vm_type: VMType | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=100),
) -> Response:
    """Get just the VMs table (for HTMX partial updates)."""
    offset = (page - 1) * page_size
    vms, total = await proxmox_service.get_all_vms(
        hypervisor_id=hypervisor,
        state=state,
        vm_type=vm_type,
        limit=page_size,
        offset=offset,
    )

    total_pages = (total + page_size - 1) // page_size

    return templates.TemplateResponse(
        "vms/_table.html",
        {
            "request": request,
            "vms": vms,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
    )


@router.get("/{vm_id}", response_class=HTMLResponse)
async def vm_detail(
    request: Request,
    vm_id: int,
    user: AuthenticatedUser,
    templates: Templates,
    proxmox_service: ProxmoxServiceDep,
) -> Response:
    """Display VM detail page."""
    vm = await proxmox_service.get_vm_by_id(vm_id)

    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")

    return templates.TemplateResponse(
        "vms/detail.html",
        {
            "request": request,
            "user": user,
            "vm": vm,
        },
    )


# API endpoints


@router.post("/sync/{integration_id}")
async def sync_vms(
    integration_id: str,
    user: AuthenticatedUser,
    proxmox_service: ProxmoxServiceDep,
) -> VMSyncResult:
    """Trigger a VM sync from a Proxmox integration."""
    try:
        result = await proxmox_service.sync_proxmox(integration_id)
        return VMSyncResult(
            hypervisor_id=result.hypervisor_id,
            vms_created=result.vms_created,
            vms_updated=result.vms_updated,
            vms_removed=result.vms_removed,
            hosts_linked=result.hosts_linked,
            snapshots_synced=result.snapshots_synced,
            timestamp=result.timestamp,
            error=result.error,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/sync")
async def sync_all_vms(
    user: AuthenticatedUser,
    proxmox_service: ProxmoxServiceDep,
) -> list[VMSyncResult]:
    """Trigger a sync from all configured Proxmox integrations."""
    results = await proxmox_service.sync_all_proxmox()
    return [
        VMSyncResult(
            hypervisor_id=r.hypervisor_id,
            vms_created=r.vms_created,
            vms_updated=r.vms_updated,
            vms_removed=r.vms_removed,
            hosts_linked=r.hosts_linked,
            snapshots_synced=r.snapshots_synced,
            timestamp=r.timestamp,
            error=r.error,
        )
        for r in results
    ]


@router.get("/api/{vm_id}", response_model=VMDetailResponse)
async def get_vm_api(
    vm_id: int,
    user: AuthenticatedUser,
    proxmox_service: ProxmoxServiceDep,
) -> VMDetailResponse:
    """Get VM by ID (JSON API)."""
    vm = await proxmox_service.get_vm_by_id(vm_id)

    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")

    # Convert to response with relationships
    hypervisor_resp = None
    if vm.hypervisor:
        hypervisor_resp = HypervisorResponse.model_validate(vm.hypervisor)

    snapshots_resp = [VMSnapshotResponse.model_validate(s) for s in vm.snapshots]

    return VMDetailResponse(
        id=vm.id,
        uuid=vm.uuid,
        name=vm.name,
        vmid=vm.vmid,
        vm_type=vm.vm_type,
        hypervisor_id=vm.hypervisor_id,
        host_id=vm.host_id,
        state=vm.state,
        vcpus=vm.vcpus,
        memory_mb=vm.memory_mb,
        disk_gb=vm.disk_gb,
        mac_addresses=vm.mac_addresses,
        uptime_seconds=vm.uptime_seconds,
        tags=vm.tags,
        last_state_change=vm.last_state_change,
        description=vm.description,
        created_at=vm.created_at,
        updated_at=vm.updated_at,
        hypervisor=hypervisor_resp,
        snapshots=snapshots_resp,
    )


@router.get("/api/stats", response_model=VMStatsResponse)
async def get_vm_stats(
    user: AuthenticatedUser,
    proxmox_service: ProxmoxServiceDep,
) -> VMStatsResponse:
    """Get VM statistics."""
    stats = await proxmox_service.get_vm_stats()
    return VMStatsResponse(**stats)


@router.get("/api/hypervisors", response_model=list[HypervisorResponse])
async def get_hypervisors(
    user: AuthenticatedUser,
    proxmox_service: ProxmoxServiceDep,
) -> list[HypervisorResponse]:
    """Get all hypervisors."""
    hypervisors = await proxmox_service.get_hypervisors()
    return [HypervisorResponse.model_validate(h) for h in hypervisors]
