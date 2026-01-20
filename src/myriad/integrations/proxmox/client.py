"""Proxmox VE API client for VM discovery and management."""

import logging
import re
from dataclasses import dataclass, field

import httpx

from myriad.config import ProxmoxCredentials, ProxmoxIntegrationConfig

logger = logging.getLogger(__name__)


@dataclass
class ProxmoxNode:
    """Represents a Proxmox cluster node."""

    name: str
    status: str
    cpu: float | None = None
    memory_used: int | None = None
    memory_total: int | None = None
    uptime: int | None = None


@dataclass
class ProxmoxVM:
    """Represents a VM or container from Proxmox."""

    vmid: int
    name: str
    node: str
    vm_type: str  # "qemu" or "lxc"
    status: str
    cpu: float | None = None
    memory: int | None = None  # Current memory in bytes
    maxmem: int | None = None  # Max memory in bytes
    disk: int | None = None  # Disk usage in bytes
    maxdisk: int | None = None  # Max disk in bytes
    uptime: int | None = None
    tags: str | None = None
    mac_addresses: list[str] = field(default_factory=list)
    template: bool = False

    @property
    def uuid(self) -> str:
        """Generate a consistent UUID-like identifier from node and vmid."""
        # Proxmox doesn't expose a true UUID, so we generate a deterministic one
        # Format: 00000000-0000-vmid-node-hash
        import hashlib

        node_hash = hashlib.md5(self.node.encode()).hexdigest()[:12]
        vmid_padded = f"{self.vmid:08d}"
        return f"00000000-0000-{vmid_padded[:4]}-{vmid_padded[4:]}-{node_hash}"


class ProxmoxClient:
    """Async client for Proxmox VE REST API."""

    def __init__(
        self,
        config: ProxmoxIntegrationConfig,
        credentials: ProxmoxCredentials,
    ):
        self.config = config
        self.credentials = credentials
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ProxmoxClient":
        """Enter async context."""
        # Build authorization header
        auth_header = f"PVEAPIToken={self.credentials.token_id}={self.credentials.token_secret}"

        self._client = httpx.AsyncClient(
            base_url=f"{self.config.base_url}/api2/json",
            headers={"Authorization": auth_header},
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
        """Test the connection to Proxmox and return True if successful."""
        try:
            response = await self.client.get("/version")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Proxmox connection test failed: {e}")
            return False

    async def get_version(self) -> str | None:
        """Get the Proxmox VE version."""
        try:
            response = await self.client.get("/version")
            response.raise_for_status()
            data = response.json()
            return data.get("data", {}).get("version")
        except Exception as e:
            logger.error(f"Failed to get Proxmox version: {e}")
            return None

    async def get_nodes(self) -> list[ProxmoxNode]:
        """Get all nodes in the cluster."""
        try:
            response = await self.client.get("/nodes")
            response.raise_for_status()
            data = response.json()

            nodes = []
            for node_data in data.get("data", []):
                node = ProxmoxNode(
                    name=node_data.get("node", ""),
                    status=node_data.get("status", "unknown"),
                    cpu=node_data.get("cpu"),
                    memory_used=node_data.get("mem"),
                    memory_total=node_data.get("maxmem"),
                    uptime=node_data.get("uptime"),
                )
                nodes.append(node)

            return nodes
        except Exception as e:
            logger.error(f"Failed to get Proxmox nodes: {e}")
            raise

    async def get_all_vms(self) -> list[ProxmoxVM]:
        """Get all VMs and containers from the cluster.

        Uses /cluster/resources for efficient listing, then fetches config
        for each VM to get MAC addresses.
        """
        try:
            response = await self.client.get("/cluster/resources", params={"type": "vm"})
            response.raise_for_status()
            data = response.json()

            vms = []
            for vm_data in data.get("data", []):
                # Skip templates unless explicitly wanted
                if vm_data.get("template", 0) == 1:
                    continue

                # Filter by node if configured
                if self.config.node and vm_data.get("node") != self.config.node:
                    continue

                vm_type = vm_data.get("type", "qemu")
                node = vm_data.get("node", "")
                vmid = vm_data.get("vmid", 0)

                # Fetch config to get MAC addresses
                mac_addresses = await self._get_vm_mac_addresses(node, vmid, vm_type)

                vm = ProxmoxVM(
                    vmid=vmid,
                    name=vm_data.get("name", f"vm-{vmid}"),
                    node=node,
                    vm_type=vm_type,
                    status=vm_data.get("status", "unknown"),
                    cpu=vm_data.get("cpu"),
                    memory=vm_data.get("mem"),
                    maxmem=vm_data.get("maxmem"),
                    disk=vm_data.get("disk"),
                    maxdisk=vm_data.get("maxdisk"),
                    uptime=vm_data.get("uptime"),
                    tags=vm_data.get("tags"),
                    mac_addresses=mac_addresses,
                    template=vm_data.get("template", 0) == 1,
                )
                vms.append(vm)

            logger.info(f"Found {len(vms)} VMs/containers from Proxmox")
            return vms

        except Exception as e:
            logger.error(f"Failed to get Proxmox VMs: {e}")
            raise

    async def _get_vm_mac_addresses(self, node: str, vmid: int, vm_type: str) -> list[str]:
        """Fetch MAC addresses from VM/container config."""
        try:
            endpoint = f"/nodes/{node}/{vm_type}/{vmid}/config"
            response = await self.client.get(endpoint)

            if response.status_code != 200:
                logger.debug(f"Could not fetch config for {vm_type}/{vmid}: {response.status_code}")
                return []

            config = response.json().get("data", {})
            return self._extract_mac_addresses(config, vm_type)

        except Exception as e:
            logger.debug(f"Failed to get MAC addresses for {vm_type}/{vmid}: {e}")
            return []

    def _extract_mac_addresses(self, config: dict, vm_type: str) -> list[str]:
        """Extract MAC addresses from VM/container config.

        QEMU format: net0: "virtio=BC:24:11:XX:XX:XX,bridge=vmbr0"
        LXC format: net0: "name=eth0,hwaddr=BC:24:11:XX:XX:XX,bridge=vmbr0"
        """
        macs = []

        # Look for net0, net1, net2, etc.
        for key, value in config.items():
            if not key.startswith("net") or not isinstance(value, str):
                continue

            mac = self._parse_mac_from_netconfig(value, vm_type)
            if mac:
                macs.append(self._normalize_mac(mac))

        return macs

    def _parse_mac_from_netconfig(self, net_config: str, vm_type: str) -> str | None:
        """Parse MAC address from network config string."""
        if vm_type == "lxc":
            # LXC: "name=eth0,hwaddr=BC:24:11:XX:XX:XX,bridge=vmbr0"
            match = re.search(r"hwaddr=([A-Fa-f0-9:]+)", net_config)
            if match:
                return match.group(1)
        else:
            # QEMU: "virtio=BC:24:11:XX:XX:XX,bridge=vmbr0"
            # Also handles: "model=virtio,macaddr=XX:XX:XX:XX:XX:XX"
            # Try macaddr= first (newer format)
            match = re.search(r"macaddr=([A-Fa-f0-9:]+)", net_config, re.IGNORECASE)
            if match:
                return match.group(1)

            # Try the = format (virtio=MAC,bridge=...)
            parts = net_config.split(",")
            if parts:
                first_part = parts[0]
                if "=" in first_part:
                    _, mac_candidate = first_part.split("=", 1)
                    # Check if it looks like a MAC address
                    if re.match(r"^[A-Fa-f0-9:]{17}$", mac_candidate):
                        return mac_candidate

        return None

    async def get_vm_snapshots(self, node: str, vmid: int, vm_type: str) -> list[dict]:
        """Get snapshots for a VM or container."""
        try:
            endpoint = f"/nodes/{node}/{vm_type}/{vmid}/snapshot"
            response = await self.client.get(endpoint)
            response.raise_for_status()
            data = response.json()

            snapshots = []
            for snap in data.get("data", []):
                # Skip the "current" pseudo-snapshot
                if snap.get("name") == "current":
                    continue
                snapshots.append(
                    {
                        "name": snap.get("name"),
                        "description": snap.get("description"),
                        "snaptime": snap.get("snaptime"),
                        "parent": snap.get("parent"),
                    }
                )

            return snapshots
        except Exception as e:
            logger.debug(f"Failed to get snapshots for {vm_type}/{vmid}: {e}")
            return []

    @staticmethod
    def _normalize_mac(mac: str) -> str:
        """Normalize MAC address to lowercase with colons."""
        mac = mac.lower().replace("-", ":")
        # Already in correct format if it has colons and is 17 chars
        if len(mac) == 17 and mac.count(":") == 5:
            return mac

        # Handle other formats
        clean = mac.replace(":", "").replace(".", "")
        if len(clean) == 12:
            return ":".join(clean[i : i + 2] for i in range(0, 12, 2))

        return mac


async def create_proxmox_client(
    config: ProxmoxIntegrationConfig,
    credentials: ProxmoxCredentials,
) -> ProxmoxClient:
    """Create and return a Proxmox client (for use with async with)."""
    return ProxmoxClient(config, credentials)
