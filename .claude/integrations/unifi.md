# Unifi Integration (Phase 3)

Integration for discovering WiFi clients from Unifi controllers.

## Status: Planned

This integration is planned for Phase 3 development.

## Planned Features

- Connect to Unifi controller API
- Discover connected WiFi clients
- Enrich existing hosts with WiFi-specific data (signal strength, AP, etc.)
- Track device roaming between APs

## Configuration (Planned)

```toml
[[integrations.unifi]]
id = "unifi-main"
base_url = "https://10.0.1.2:8443"
credentials_ref = "unifi.main"
site = "default"
location_id = "home-lan"
```

## Unifi API Notes

The Unifi controller API is not officially documented. Key endpoints:

- `POST /api/login` - Authentication
- `GET /api/s/{site}/stat/sta` - Connected clients
- `GET /api/s/{site}/stat/device` - Access points

## Implementation Notes

<!-- Add notes here as development progresses -->
