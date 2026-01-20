# Myriad

Home infrastructure management system for discovering, tracking, and managing network devices across home/lab environments.

## Tech Stack

- **Backend**: FastAPI 0.109+ with async/await throughout
- **Database**: SQLAlchemy 2.0 async + SQLite (aiosqlite) + Alembic migrations
- **Frontend**: Jinja2 templates + HTMX 1.9 (no JavaScript frameworks)
- **Integrations**: OPNsense (Phase 1), libvirt (Phase 2), Unifi (Phase 3)
- **Config**: TOML-based with pydantic-settings validation
- **Linting**: Ruff (E, F, I, UP, B rules)

## Critical Rules

### Security

- NEVER commit `config/secrets.toml` or expose credentials
- NEVER disable SSL verification in production integrations
- ALWAYS use parameterized queries (SQLAlchemy handles this)
- ALWAYS hash passwords with passlib bcrypt

### Breaking Changes (Ask First)

Stop and ask before making changes that could break existing functionality:

- Removing or renaming public API endpoints
- Changing database schema in non-additive ways
- Removing features or deprecating code paths
- Changing authentication/session behavior

### Autonomous Actions (No Approval Needed)

- Adding new features following existing patterns
- Bug fixes that don't change API contracts
- Adding tests, improving coverage
- Code refactoring that preserves behavior
- New integration clients following established patterns
- Adding new Alembic migrations (additive schema changes)

### Code Quality

- ALWAYS use async/await - never sync database operations
- ALWAYS add type hints to all function signatures
- ALWAYS run verification commands before committing
- NEVER add JavaScript when HTMX can accomplish the goal

### Testing (Strict TDD)

- ALWAYS write or update tests for every code change
- Tests go in `tests/` mirroring `src/myriad/` structure
- Use pytest-asyncio for async test functions
- Use httpx.AsyncClient for endpoint testing

## Commit Convention

Use conventional commits:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation only
- `refactor:` - Code change that neither fixes nor adds
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

Examples:
```
feat: add host filtering by location
fix: correct MAC address normalization for uppercase input
refactor: extract DHCP lease parsing to separate function
test: add coverage for sync_service edge cases
```

## Code Patterns

### Database Operations

Always use AsyncSession via dependency injection:

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def get_host_by_mac(db: AsyncSession, mac: str) -> Host | None:
    result = await db.execute(select(Host).where(Host.mac_address == mac))
    return result.scalar_one_or_none()
```

### Service Layer

Business logic lives in `services/`. Routers handle HTTP and delegate to services:

```python
# In services/host_service.py
async def upsert_host(db: AsyncSession, data: HostUpsert) -> Host:
    existing = await get_host_by_mac(db, data.mac_address)
    if existing:
        # Update existing
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(existing, key, value)
        return existing
    # Create new
    host = Host(**data.model_dump())
    db.add(host)
    return host
```

### HTMX Endpoints

Return HTML fragments for HTMX requests, full pages for direct browser requests:

```python
@router.get("/hosts/table")
async def hosts_table(
    request: Request,
    db: AsyncSession = Depends(get_db),
    location: str | None = None,
    status: str | None = None,
):
    hosts = await host_service.list_hosts(db, location=location, status=status)
    return templates.TemplateResponse(
        "hosts/_table.html",
        {"request": request, "hosts": hosts}
    )
```

### Pydantic Schemas

Use separate schemas for create, update, and response:

```python
class HostBase(BaseModel):
    hostname: str | None = None
    display_name: str | None = None

class HostCreate(HostBase):
    mac_address: str  # Required for creation

class HostUpdate(HostBase):
    pass  # All fields optional

class HostResponse(HostBase):
    id: int
    mac_address: str
    status: HostStatus
    model_config = ConfigDict(from_attributes=True)
```

## Project Structure

```
src/myriad/
├── main.py            # FastAPI app factory & CLI entry point
├── config.py          # TOML configuration loading
├── core/              # Database, security, dependencies
│   ├── database.py    # AsyncSession management
│   ├── security.py    # Password hashing, session tokens
│   └── dependencies.py # FastAPI dependency injection
├── models/            # SQLAlchemy ORM models
├── schemas/           # Pydantic request/response schemas
├── routers/           # FastAPI route handlers
├── services/          # Business logic layer
└── integrations/      # External API clients
    ├── opnsense/      # OPNsense firewall (Phase 1)
    ├── libvirt/       # Hypervisor management (Phase 2)
    └── unifi/         # WiFi controller (Phase 3)
```

## Verification Commands

Run before committing:

```bash
ruff check src/                    # Lint
ruff format src/ --check           # Format check
pytest                             # Tests (required to pass)
alembic upgrade head               # Verify migrations apply cleanly
```

## Configuration

### Main Config: `config/myriad.toml`

```toml
[server]
host = "0.0.0.0"
port = 8000
debug = true

[database]
url = "sqlite+aiosqlite:///./myriad.db"

[[locations]]
id = "home-lan"
name = "Home LAN"
network_cidr = "10.0.1.0/24"

[[integrations.opnsense]]
id = "opnsense-main"
base_url = "https://192.168.1.1"
credentials_ref = "opnsense.main"
location_id = "home-lan"
```

### Secrets: `config/secrets.toml` (NOT in git)

```toml
[opnsense.main]
api_key = "..."
api_secret = "..."
```

## Lessons Learned

<!--
Add entries here when Claude makes mistakes.
Format: - [Date]: Description of mistake → What to do instead
-->

## See Also

- `.claude/integrations/opnsense.md` - OPNsense API patterns and quirks
- `.claude/integrations/libvirt.md` - Hypervisor integration patterns (Phase 2)
- `.claude/integrations/unifi.md` - Unifi controller patterns (Phase 3)
