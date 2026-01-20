"""Configuration loading from TOML files."""

from pathlib import Path
from typing import Any

import toml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ServerConfig(BaseModel):
    """Server configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False


class DatabaseConfig(BaseModel):
    """Database configuration."""

    url: str = "sqlite+aiosqlite:///./myriad.db"


class LocationConfig(BaseModel):
    """Network location configuration."""

    id: str
    name: str
    network_cidr: str | None = None


class OPNsenseIntegrationConfig(BaseModel):
    """OPNsense integration configuration."""

    id: str
    base_url: str
    credential_ref: str
    location_id: str | None = None
    verify_ssl: bool = True


class UnifiIntegrationConfig(BaseModel):
    """Unifi Controller integration configuration."""

    id: str
    base_url: str
    credential_ref: str
    site: str = "default"
    location_id: str | None = None
    verify_ssl: bool = True


class HypervisorConfig(BaseModel):
    """Hypervisor configuration (legacy SSH-based)."""

    id: str
    name: str | None = None
    ssh_host: str
    ssh_port: int = 22
    ssh_user: str = "root"
    ssh_key_ref: str
    location_id: str | None = None


class ProxmoxIntegrationConfig(BaseModel):
    """Proxmox VE integration configuration."""

    id: str
    base_url: str  # e.g., "https://192.168.1.10:8006"
    credential_ref: str  # e.g., "proxmox.borgcube"
    node: str | None = None  # Filter to specific node, None = all nodes
    location_id: str | None = None
    verify_ssl: bool = True


class IntegrationsConfig(BaseModel):
    """All integrations configuration."""

    opnsense: list[OPNsenseIntegrationConfig] = Field(default_factory=list)
    unifi: list[UnifiIntegrationConfig] = Field(default_factory=list)
    proxmox: list[ProxmoxIntegrationConfig] = Field(default_factory=list)


class OPNsenseCredentials(BaseModel):
    """OPNsense API credentials."""

    api_key: str
    api_secret: str


class UnifiCredentials(BaseModel):
    """Unifi Controller credentials."""

    username: str
    password: str


class SSHKeyConfig(BaseModel):
    """SSH key configuration."""

    key_path: str
    passphrase: str | None = None


class ProxmoxCredentials(BaseModel):
    """Proxmox API token credentials."""

    token_id: str  # e.g., "root@pam!myriad"
    token_secret: str  # UUID format token


class SecretsConfig(BaseModel):
    """Secrets configuration loaded from secrets.toml."""

    opnsense: dict[str, OPNsenseCredentials] = Field(default_factory=dict)
    unifi: dict[str, UnifiCredentials] = Field(default_factory=dict)
    ssh: dict[str, SSHKeyConfig] = Field(default_factory=dict)
    proxmox: dict[str, ProxmoxCredentials] = Field(default_factory=dict)


class Settings(BaseSettings):
    """Application settings loaded from TOML files."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    locations: list[LocationConfig] = Field(default_factory=list)
    integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)
    hypervisors: list[HypervisorConfig] = Field(default_factory=list)
    secrets: SecretsConfig = Field(default_factory=SecretsConfig)

    # Session configuration
    session_secret_key: str = "change-me-in-production"
    session_expire_hours: int = 24

    # Paths
    config_dir: Path = Path("config")
    templates_dir: Path = Path("templates")
    static_dir: Path = Path("static")

    model_config = {"extra": "ignore"}


def load_toml_file(path: Path) -> dict[str, Any]:
    """Load a TOML file, returning empty dict if not found."""
    if path.exists():
        return toml.load(path)
    return {}


def parse_secrets(secrets_data: dict[str, Any]) -> SecretsConfig:
    """Parse secrets data into SecretsConfig."""
    opnsense_creds = {}
    unifi_creds = {}
    ssh_keys = {}
    proxmox_creds = {}

    # Parse OPNsense credentials
    if "opnsense" in secrets_data:
        for key, value in secrets_data["opnsense"].items():
            opnsense_creds[key] = OPNsenseCredentials(**value)

    # Parse Unifi credentials
    if "unifi" in secrets_data:
        for key, value in secrets_data["unifi"].items():
            unifi_creds[key] = UnifiCredentials(**value)

    # Parse SSH keys
    if "ssh" in secrets_data:
        for key, value in secrets_data["ssh"].items():
            ssh_keys[key] = SSHKeyConfig(**value)

    # Parse Proxmox credentials
    if "proxmox" in secrets_data:
        for key, value in secrets_data["proxmox"].items():
            proxmox_creds[key] = ProxmoxCredentials(**value)

    return SecretsConfig(
        opnsense=opnsense_creds,
        unifi=unifi_creds,
        ssh=ssh_keys,
        proxmox=proxmox_creds,
    )


def load_settings(config_dir: Path | None = None) -> Settings:
    """Load settings from TOML configuration files.

    Args:
        config_dir: Path to configuration directory. Defaults to ./config

    Returns:
        Populated Settings object
    """
    if config_dir is None:
        config_dir = Path("config")

    config_path = config_dir / "myriad.toml"
    secrets_path = config_dir / "secrets.toml"

    config_data = load_toml_file(config_path)
    secrets_data = load_toml_file(secrets_path)

    # Parse integrations if present
    integrations_data = config_data.pop("integrations", {})
    integrations = IntegrationsConfig(
        opnsense=[
            OPNsenseIntegrationConfig(**item) for item in integrations_data.get("opnsense", [])
        ],
        unifi=[UnifiIntegrationConfig(**item) for item in integrations_data.get("unifi", [])],
        proxmox=[ProxmoxIntegrationConfig(**item) for item in integrations_data.get("proxmox", [])],
    )

    # Parse locations if present
    locations = [LocationConfig(**loc) for loc in config_data.pop("locations", [])]

    # Parse hypervisors if present
    hypervisors = [HypervisorConfig(**hv) for hv in config_data.pop("hypervisors", [])]

    # Parse secrets
    secrets = parse_secrets(secrets_data)

    return Settings(
        **config_data,
        locations=locations,
        integrations=integrations,
        hypervisors=hypervisors,
        secrets=secrets,
        config_dir=config_dir,
    )


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def init_settings(config_dir: Path | None = None) -> Settings:
    """Initialize settings from a specific config directory."""
    global _settings
    _settings = load_settings(config_dir)
    return _settings
