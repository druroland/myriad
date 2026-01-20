# Infrastructure Connection Details

SSH connection details for managed infrastructure.

## Network Devices

| Device | Connection | Purpose |
|--------|------------|---------|
| OPNsense Router | `root@192.168.1.1` | Firewall/router, DHCP server |
| Local Server | `root@192.168.1.10` | Primary server |

## Notes

- OPNsense API access is configured separately in `config/myriad.toml` and `config/secrets.toml`
- See `.claude/integrations/opnsense.md` for API integration patterns
