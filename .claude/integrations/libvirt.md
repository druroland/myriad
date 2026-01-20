# libvirt Integration (Phase 2)

SSH-based integration for discovering and managing KVM/QEMU virtual machines via libvirt.

## Status: Planned

This integration is planned for Phase 2 development.

## Planned Features

- Connect to hypervisors via SSH + asyncssh
- Discover running and stopped VMs
- Track VM state (running, stopped, paused, etc.)
- Map VMs to network hosts via MAC addresses
- Snapshot tracking

## Architecture Notes

```
src/myriad/integrations/libvirt/
├── __init__.py
├── client.py      # SSH connection management
└── models.py      # VM state dataclasses
```

## Configuration (Planned)

```toml
[[hypervisors]]
id = "proxmox-1"
name = "Main Hypervisor"
ssh_host = "10.0.1.5"
ssh_port = 22
ssh_user = "root"
ssh_key_ref = "ssh.proxmox"
location_id = "home-lan"
```

## libvirt Commands Reference

```bash
# List all VMs
virsh list --all

# Get VM info
virsh dominfo <vm-name>

# Get VM XML (includes MAC addresses)
virsh dumpxml <vm-name>

# List snapshots
virsh snapshot-list <vm-name>
```

## Implementation Notes

<!-- Add notes here as development progresses -->
