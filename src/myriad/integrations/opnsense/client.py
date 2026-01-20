"""OPNsense API client for DHCP lease discovery."""

import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

from myriad.config import OPNsenseCredentials, OPNsenseIntegrationConfig

logger = logging.getLogger(__name__)


@dataclass
class DHCPLease:
    """Represents a DHCP lease from OPNsense."""

    mac_address: str
    ip_address: str
    hostname: str | None
    is_static: bool
    starts: datetime | None = None
    ends: datetime | None = None
    description: str | None = None


class OPNsenseClient:
    """Async client for OPNsense REST API."""

    def __init__(
        self,
        config: OPNsenseIntegrationConfig,
        credentials: OPNsenseCredentials,
    ):
        self.config = config
        self.credentials = credentials
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "OPNsenseClient":
        """Enter async context."""
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            auth=(self.credentials.api_key, self.credentials.api_secret),
            verify=self.config.verify_ssl,
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client, raising if not in context."""
        if self._client is None:
            raise RuntimeError("Client must be used within async context manager")
        return self._client

    async def test_connection(self) -> bool:
        """Test the connection to OPNsense."""
        try:
            response = await self.client.get("/api/core/firmware/status")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"OPNsense connection test failed: {e}")
            return False

    async def get_dhcp_leases(self) -> list[DHCPLease]:
        """Get all DHCP leases (dynamic)."""
        try:
            response = await self.client.get("/api/dhcpv4/leases/searchLease")
            response.raise_for_status()
            data = response.json()

            leases = []
            for row in data.get("rows", []):
                lease = self._parse_dynamic_lease(row)
                if lease:
                    leases.append(lease)

            return leases
        except Exception as e:
            logger.error(f"Failed to get DHCP leases: {e}")
            raise

    async def get_static_mappings(self) -> list[DHCPLease]:
        """Get all static DHCP mappings."""
        try:
            response = await self.client.get("/api/dhcpv4/reservations/searchReservation")
            response.raise_for_status()
            data = response.json()

            leases = []
            for row in data.get("rows", []):
                lease = self._parse_static_mapping(row)
                if lease:
                    leases.append(lease)

            return leases
        except Exception as e:
            logger.error(f"Failed to get static mappings: {e}")
            raise

    async def get_all_hosts(self) -> list[DHCPLease]:
        """Get all hosts (both dynamic leases and static mappings)."""
        dynamic_leases = await self.get_dhcp_leases()
        static_mappings = await self.get_static_mappings()

        # Create a dict keyed by MAC to deduplicate (static takes precedence)
        hosts_by_mac: dict[str, DHCPLease] = {}

        for lease in dynamic_leases:
            mac = self._normalize_mac(lease.mac_address)
            hosts_by_mac[mac] = lease

        for mapping in static_mappings:
            mac = self._normalize_mac(mapping.mac_address)
            hosts_by_mac[mac] = mapping  # Static overwrites dynamic

        return list(hosts_by_mac.values())

    def _parse_dynamic_lease(self, row: dict) -> DHCPLease | None:
        """Parse a dynamic lease from API response."""
        mac = row.get("mac")
        ip = row.get("address")

        if not mac or not ip:
            return None

        # Parse timestamps
        starts = None
        ends = None
        if row.get("starts"):
            try:
                starts = datetime.fromisoformat(row["starts"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        if row.get("ends"):
            try:
                ends = datetime.fromisoformat(row["ends"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return DHCPLease(
            mac_address=self._normalize_mac(mac),
            ip_address=ip,
            hostname=row.get("hostname") or row.get("client-hostname"),
            is_static=False,
            starts=starts,
            ends=ends,
        )

    def _parse_static_mapping(self, row: dict) -> DHCPLease | None:
        """Parse a static mapping from API response."""
        mac = row.get("mac")
        ip = row.get("ipaddr")

        if not mac or not ip:
            return None

        return DHCPLease(
            mac_address=self._normalize_mac(mac),
            ip_address=ip,
            hostname=row.get("hostname"),
            is_static=True,
            description=row.get("descr"),
        )

    @staticmethod
    def _normalize_mac(mac: str) -> str:
        """Normalize MAC address to lowercase with colons."""
        mac = mac.lower().replace("-", ":").replace(".", ":")
        # Handle cases like aa:bb:cc:dd:ee:ff or aabb.ccdd.eeff
        parts = mac.split(":")
        if len(parts) == 3:
            # Cisco format aa:bb.cc:dd.ee:ff -> split each part
            expanded = []
            for part in parts:
                expanded.extend([part[i : i + 2] for i in range(0, len(part), 2)])
            parts = expanded
        elif len(parts) != 6:
            # Try removing all separators and rebuilding
            clean = mac.replace(":", "")
            if len(clean) == 12:
                parts = [clean[i : i + 2] for i in range(0, 12, 2)]
            else:
                return mac  # Return as-is if we can't parse

        return ":".join(parts)


async def create_opnsense_client(
    config: OPNsenseIntegrationConfig,
    credentials: OPNsenseCredentials,
) -> OPNsenseClient:
    """Create and return an OPNsense client (for use with async with)."""
    return OPNsenseClient(config, credentials)
