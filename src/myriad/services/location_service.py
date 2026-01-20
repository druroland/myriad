"""Location service for managing network locations."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from myriad.models import Host, Location
from myriad.schemas import LocationCreate, LocationUpdate


class LocationService:
    """Service for location CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self) -> list[Location]:
        """Get all locations."""
        result = await self.db.execute(select(Location).order_by(Location.name))
        return list(result.scalars().all())

    async def get_by_id(self, location_id: str) -> Location | None:
        """Get a location by ID."""
        result = await self.db.execute(select(Location).where(Location.id == location_id))
        return result.scalar_one_or_none()

    async def create(self, data: LocationCreate) -> Location:
        """Create a new location."""
        location = Location(
            id=data.id,
            name=data.name,
            network_cidr=data.network_cidr,
            description=data.description,
        )
        self.db.add(location)
        await self.db.flush()
        return location

    async def update(self, location: Location, data: LocationUpdate) -> Location:
        """Update an existing location."""
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(location, field, value)

        await self.db.flush()
        return location

    async def delete(self, location: Location) -> None:
        """Delete a location."""
        await self.db.delete(location)
        await self.db.flush()

    async def get_with_host_counts(self) -> list[dict]:
        """Get all locations with their host counts."""
        # Query locations with host counts
        query = (
            select(Location, func.count(Host.id).label("host_count"))
            .outerjoin(Host, Location.id == Host.location_id)
            .group_by(Location.id)
            .order_by(Location.name)
        )

        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "location": row.Location,
                "host_count": row.host_count,
            }
            for row in rows
        ]

    async def ensure_from_config(self, location_id: str, name: str, network_cidr: str | None) -> Location:
        """Ensure a location exists from config, creating if necessary."""
        location = await self.get_by_id(location_id)

        if location:
            # Update if needed
            if location.name != name or location.network_cidr != network_cidr:
                location.name = name
                location.network_cidr = network_cidr
                await self.db.flush()
        else:
            # Create new
            location = Location(
                id=location_id,
                name=name,
                network_cidr=network_cidr,
            )
            self.db.add(location)
            await self.db.flush()

        return location
