# Sync Integrations

Trigger a sync from configured integrations and report results.

## Steps

1. Check if the server is running:
   ```bash
   curl -s http://localhost:8000/health || echo "Server not running"
   ```

2. If server is running, trigger sync via API:
   ```bash
   curl -X POST http://localhost:8000/hosts/sync \
     -H "Cookie: session=<session_id>" \
     -H "Content-Type: application/json"
   ```

3. If server is not running, suggest starting it:
   ```bash
   myriad --reload --debug
   ```

4. Report sync results:
   - Number of hosts discovered
   - Number of hosts created vs updated
   - Any errors encountered

## Manual Sync (Without Server)

If you need to test sync logic directly:

```python
from myriad.services.sync_service import SyncService
from myriad.core.database import get_db

async with get_db() as db:
    service = SyncService(db)
    results = await service.sync_all()
    print(results)
```

## Troubleshooting

- **Connection refused**: Check OPNsense is reachable and credentials are correct
- **SSL errors**: Verify `verify_ssl` setting in config
- **No hosts found**: Check the DHCP server has active leases
