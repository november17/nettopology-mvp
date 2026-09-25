# NetTopology MVP

Ubuntu desktop visual network topology and configuration planner.

## MVP features

- Add individual devices with type and operating system
- Set the number of physical/logical ports
- Assign a MAC address to every port
- Visual port-to-port topology links
- Create LAN, VLAN, WAN, WiFi and Guest networks
- Assign VLAN IDs, CIDRs, gateways and WiFi metadata
- Router-aware configuration planning
- Multiple router bridges are represented in the project model and can be extended in the UI
- Generate a reviewable addressing, routing and firewall plan
- Save/open topology projects as JSON

## Install on Ubuntu

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip && cd /path/to/nettopology && python3 -m venv .venv && . .venv/bin/activate && pip install --upgrade pip PySide6 && python nettopology.py
```

## Design direction

The configuration engine deliberately produces a plan rather than silently applying network changes. The next production phase should add OS-specific generators, validation, IPAM/subnet allocation, DHCP/DNS modeling, firewall zones, NAT, routing protocols, bridge membership, WiFi interfaces, and import/export for common vendor formats.
