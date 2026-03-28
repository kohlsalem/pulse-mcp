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

The server supports two deployment modes:

- **Local (stdio)** — runs as a subprocess of your MCP client (Claude Code, Claude Desktop, etc.)
- **Docker (HTTP)** — runs as a standalone HTTP server with Basic Auth, suitable for shared or remote access

### Pulse credentials

Both modes need access to your Pulse instance. Authenticate via **API token** (recommended) or **username/password**:

| Variable | Description |
|---|---|
| `PULSE_URL` | Pulse instance URL (e.g. `https://pulse.example.com`) |
| `PULSE_API_TOKEN` | API token (create in Pulse Settings > Security) |
| `PULSE_USERNAME` | Username (fallback if no token) |
| `PULSE_PASSWORD` | Password (fallback if no token) |
| `PULSE_SKIP_TLS_VERIFY` | Set `true` for self-signed certs |

---

### Option 1: Local (stdio)

#### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A running [Pulse](https://github.com/rcourtman/Pulse) instance

#### Install

```bash
git clone https://github.com/kohlsalem/pulse-mcp.git
cd pulse-mcp
uv sync
```

#### Configure

```bash
cp .env.example .env
# Edit .env with your Pulse URL and credentials
```

#### Add to Claude Code

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

#### Manual testing

```bash
PULSE_URL=https://pulse.example.com PULSE_USERNAME=admin PULSE_PASSWORD=admin \
  uv run mcp dev src/pulse_mcp/server.py
```

---

### Option 2: Docker (HTTP with Basic Auth)

Runs the MCP server over HTTP using the streamable-http transport, protected by Basic Auth. Suitable for running behind a reverse proxy or exposing to remote MCP clients.

#### Prerequisites

- Docker (and optionally Docker Compose)
- A running [Pulse](https://github.com/rcourtman/Pulse) instance

#### Quick start with Docker Compose

1. Edit `docker-compose.yml` and fill in your credentials:

   ```yaml
   environment:
     PULSE_URL: "https://pulse.example.com"
     PULSE_API_TOKEN: "your-token-here"
     MCP_USERNAME: "your-mcp-user"
     MCP_PASSWORD: "your-mcp-password"
   ```

2. Start the server:

   ```bash
   docker compose up -d
   ```

The server listens on port 8000 by default.

#### Or build and run manually

```bash
docker build -t pulse-mcp .

docker run -d --name pulse-mcp \
  -e PULSE_URL=https://pulse.example.com \
  -e PULSE_API_TOKEN=your-token-here \
  -e MCP_USERNAME=your-mcp-user \
  -e MCP_PASSWORD=your-mcp-password \
  -p 8000:8000 \
  pulse-mcp
```

#### Connect an MCP client

Point your MCP client at the HTTP endpoint with Basic Auth credentials. For example, in Claude Code:

```bash
claude mcp add pulse -s user \
  --transport http \
  --url http://your-mcp-user:your-mcp-password@localhost:8000/mcp
```

#### HTTP environment variables

| Variable | Default | Description |
|---|---|---|
| `MCP_TRANSPORT` | `stdio` | Set to `streamable-http` for HTTP mode |
| `MCP_HOST` | `0.0.0.0` | Bind host |
| `MCP_PORT` | `8000` | Bind port |
| `MCP_USERNAME` | *(required)* | Basic Auth username |
| `MCP_PASSWORD` | *(required)* | Basic Auth password |

## License

MIT
