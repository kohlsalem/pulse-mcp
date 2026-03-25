# Pulse MCP Server

MCP server for [Pulse](https://github.com/rcourtman/Pulse), a Proxmox VE monitoring dashboard. Gives Claude (and other MCP clients) direct access to your cluster status, alerts, anomalies, and more.

## Tools

### Read (10)

| Tool | Description |
|---|---|
| `get_cluster_status` | Full overview: nodes, VMs, containers with CPU/memory/disk/uptime |
| `get_node_details` | Single node details by name |
| `get_guest_details` | Single VM or container by name or VMID |
| `get_alerts` | Active alerts, filterable by level |
| `get_alert_config` | Alert thresholds for CPU, memory, disk |
| `get_storage` | Storage pools across all nodes |
| `get_anomalies` | AI-detected anomalies (unusual resource patterns) |
| `get_health` | Server health, version, update availability |
| `get_guests_metadata` | Tags, notes, custom URLs for all guests |
| `get_system_settings` | Polling intervals, discovery config |

### Write (6)

| Tool | Description |
|---|---|
| `acknowledge_alert` | Acknowledge an alert by ID |
| `clear_alert` | Clear an alert by ID |
| `bulk_acknowledge_alerts` | Acknowledge multiple alerts at once |
| `update_guest_metadata` | Update tags, notes, or custom URL for a guest |
| `update_alert_config` | Update alert thresholds |
| `update_system_settings` | Update system settings |

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A running [Pulse](https://github.com/rcourtman/Pulse) instance

### Install

```bash
git clone https://github.com/kohlsalem/pulse-mcp.git
cd pulse-mcp
uv sync
```

### Configure

Copy `.env.example` to `.env` and fill in your Pulse URL and credentials:

```bash
cp .env.example .env
```

You can authenticate via **API token** (recommended) or **username/password**:

| Variable | Description |
|---|---|
| `PULSE_URL` | Pulse instance URL (e.g. `https://pulse.example.com`) |
| `PULSE_API_TOKEN` | API token (create in Pulse Settings > Security) |
| `PULSE_USERNAME` | Username (fallback if no token) |
| `PULSE_PASSWORD` | Password (fallback if no token) |
| `PULSE_SKIP_TLS_VERIFY` | Set `true` for self-signed certs |

### Add to Claude Code

```bash
claude mcp add pulse -s user \
  -e PULSE_URL=https://pulse.example.com \
  -e PULSE_API_TOKEN=your-token-here \
  -e PULSE_SKIP_TLS_VERIFY=true \
  -- /path/to/pulse-mcp/.venv/bin/pulse-mcp
```

Or with username/password:

```bash
claude mcp add pulse -s user \
  -e PULSE_URL=https://pulse.example.com \
  -e PULSE_USERNAME=admin \
  -e PULSE_PASSWORD=admin \
  -e PULSE_SKIP_TLS_VERIFY=true \
  -- /path/to/pulse-mcp/.venv/bin/pulse-mcp
```

Restart Claude Code. Verify with `/mcp` or:

```bash
claude mcp get pulse
```

### Manual testing

```bash
PULSE_URL=https://pulse.example.com PULSE_USERNAME=admin PULSE_PASSWORD=admin \
  uv run mcp dev src/pulse_mcp/server.py
```

## License

MIT
