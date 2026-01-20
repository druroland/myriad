"""Pydantic schemas for validation and serialization."""

from myriad.schemas.auth import LoginRequest, SetupRequest, UserCreate, UserResponse
from myriad.schemas.host import (
    HostCreate,
    HostListResponse,
    HostResponse,
    HostSyncResult,
    HostUpdate,
)
from myriad.schemas.location import LocationCreate, LocationResponse, LocationUpdate

__all__ = [
    "LoginRequest",
    "UserCreate",
    "UserResponse",
    "SetupRequest",
    "HostCreate",
    "HostUpdate",
    "HostResponse",
    "HostListResponse",
    "HostSyncResult",
    "LocationCreate",
    "LocationUpdate",
    "LocationResponse",
]
