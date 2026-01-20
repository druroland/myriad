# OPNsense Integration

API integration for discovering DHCP leases and static mappings from OPNsense firewalls.

## API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/core/firmware/status` | GET | Connection test |
| `/api/dhcpv4/leases/searchLease` | GET | Get dynamic DHCP leases |
| `/api/dhcpv4/reservations/searchReservation` | GET | Get static DHCP mappings |

## Authentication

OPNsense uses API key + secret authentication (HTTP Basic Auth):

```python
httpx.AsyncClient(
    auth=(api_key, api_secret),
    verify=verify_ssl,  # May need False for self-signed certs
)
```

API keys are created in OPNsense: System > Access > Users > [user] > API keys

## Response Formats

### Dynamic Leases (`searchLease`)

```json
{
  "rows": [
    {
      "mac": "aa:bb:cc:dd:ee:ff",
      "address": "10.0.1.50",
      "hostname": "device-name",
      "client-hostname": "device-name",
      "starts": "2024-01-15T10:30:00Z",
      "ends": "2024-01-15T22:30:00Z"
    }
  ]
}
```

### Static Mappings (`searchReservation`)

```json
{
  "rows": [
    {
      "mac": "aa:bb:cc:dd:ee:ff",
      "ipaddr": "10.0.1.10",
      "hostname": "server",
      "descr": "Main server"
    }
  ]
}
```

Note: Static uses `ipaddr`, dynamic uses `address`.

## MAC Address Normalization

OPNsense may return MACs in various formats. Always normalize to lowercase with colons:

```python
# Handles: AA:BB:CC:DD:EE:FF, aa-bb-cc-dd-ee-ff, aabb.ccdd.eeff
def _normalize_mac(mac: str) -> str:
    mac = mac.lower().replace("-", ":").replace(".", ":")
    # ... (see client.py for full implementation)
```

## Quirks and Gotchas

### Hostname Fields

Dynamic leases may have hostname in either `hostname` or `client-hostname` field. Check both:

```python
hostname = row.get("hostname") or row.get("client-hostname")
```

### Timestamp Parsing

Timestamps may have `Z` suffix instead of `+00:00`. Convert before parsing:

```python
datetime.fromisoformat(row["starts"].replace("Z", "+00:00"))
```

### Deduplication

A device may appear in both dynamic leases and static mappings. When merging, static takes precedence (it has the authoritative IP).

### SSL Verification

Self-signed certificates are common. Configuration supports `verify_ssl: false`, but log a warning in production.

## Configuration Reference

In `config/myriad.toml`:

```toml
[[integrations.opnsense]]
id = "opnsense-main"           # Unique identifier
base_url = "https://10.0.1.1"  # OPNsense web UI URL
credentials_ref = "opnsense.main"  # Reference to secrets.toml
location_id = "home-lan"       # Which location this discovers hosts for
verify_ssl = false             # For self-signed certs
```

In `config/secrets.toml`:

```toml
[opnsense.main]
api_key = "your-api-key"
api_secret = "your-api-secret"
```

## Testing the Integration

```python
async with OPNsenseClient(config, credentials) as client:
    if await client.test_connection():
        hosts = await client.get_all_hosts()
        print(f"Found {len(hosts)} hosts")
```

## Error Handling

The client raises exceptions on API errors. Callers should handle:

- `httpx.ConnectError` - Firewall unreachable
- `httpx.HTTPStatusError` - API returned error status
- `RuntimeError` - Client used outside async context
