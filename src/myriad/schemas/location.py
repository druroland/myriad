"""Location schemas for validation and responses."""

from datetime import datetime

from pydantic import BaseModel, Field


class LocationBase(BaseModel):
    """Base location fields."""

    id: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9-]+$")
    name: str = Field(..., min_length=1, max_length=100)
    network_cidr: str | None = None
    description: str | None = None


class LocationCreate(LocationBase):
    """Location creation data."""

    pass


class LocationUpdate(BaseModel):
    """Location update data (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=100)
    network_cidr: str | None = None
    description: str | None = None


class LocationResponse(LocationBase):
    """Location response data."""

    created_at: datetime
    updated_at: datetime
    host_count: int = 0

    model_config = {"from_attributes": True}
