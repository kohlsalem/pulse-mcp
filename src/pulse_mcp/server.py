"""Pulse MCP Server -- tools for monitoring and managing a Pulse instance."""

import json
import logging
import sys

from mcp.server.fastmcp import FastMCP

from pulse_mcp.client import PulseClient

# Logging to stderr only (stdout is JSON-RPC)
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("pulse-mcp")

mcp = FastMCP(
    "pulse",
    instructions=(
        "MCP server for Pulse, a Proxmox VE monitoring dashboard. "
        "Provides read access to cluster status, nodes, VMs, containers, alerts, storage, "
        "anomalies, and system health. Write tools allow acknowledging/clearing alerts and "
        "updating guest metadata and settings."
    ),
)

_client: PulseClient | None = None


def _get_client() -> PulseClient:
    global _client
    if _client is None:
        _client = PulseClient()
    return _client


def _fmt_bytes(b: int | float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return f"{b:.0f} {unit}" if b == int(b) else f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def _fmt_pct(fraction: float) -> str:
    return f"{fraction:.0f}%"


def _fmt_uptime(seconds: int) -> str:
    days, rem = divmod(seconds, 86400)
    hours, _ = divmod(rem, 3600)
    return f"{days}d {hours}h" if days else f"{hours}h"


# ═══════════════════════════════════════════════════════════════════
#  READ TOOLS
# ═══════════════════════════════════════════════════════════════════


@mcp.tool()
async def get_cluster_status() -> str:
    """Get full cluster overview: all Proxmox nodes with their VMs and containers including CPU, memory, disk usage, and uptime."""
    state = await _get_client().get_state()
    lines: list[str] = []

    # Nodes
    for n in state.get("nodes", []):
        mem = n.get("memory", {})
        disk = n.get("disk", {})
        lines.append(
            f"Node: {n['name']} ({n.get('status', '?')})  "
            f"CPU: {_fmt_pct(n.get('cpu', 0) * 100)} ({n.get('cpuInfo', {}).get('cores', '?')} cores)  "
            f"Mem: {_fmt_bytes(mem.get('used', 0))}/{_fmt_bytes(mem.get('total', 0))} ({_fmt_pct(mem.get('usage', 0))})  "
            f"Disk: {_fmt_bytes(disk.get('used', 0))}/{_fmt_bytes(disk.get('total', 0))}  "
            f"Uptime: {_fmt_uptime(n.get('uptime', 0))}"
        )

    lines.append("")

    # Guests (VMs + containers)
    guests = state.get("vms", []) + state.get("containers", [])
    guests.sort(key=lambda g: g.get("vmid", 0))
    for g in guests:
        gtype = "VM" if g.get("type") == "qemu" else "LXC"
        mem = g.get("memory", {})
        disk = g.get("disk", {})
        cpu_pct = _fmt_pct(g.get("cpu", 0) * 100)
        mem_str = f"{_fmt_bytes(mem.get('used', 0))}/{_fmt_bytes(mem.get('total', 0))}"
        disk_str = f"{_fmt_bytes(disk.get('used', 0))}/{_fmt_bytes(disk.get('total', 0))}" if disk.get("total") else "-"
        uptime_str = _fmt_uptime(g.get("uptime", 0)) if g.get("uptime") else "-"
        lines.append(
            f"  {g.get('status', '?'):8s} {gtype:3s} {g.get('vmid', '?'):>4}  {g.get('name', '?'):16s}  "
            f"CPU: {cpu_pct:>4s} ({g.get('cpus', '?')} cores)  "
            f"Mem: {mem_str}  Disk: {disk_str}  "
            f"Uptime: {uptime_str}  Node: {g.get('node', '?')}"
        )

    return "\n".join(lines)


@mcp.tool()
async def get_node_details(node_name: str) -> str:
    """Get detailed info for a specific Proxmox node by name (e.g. 'Proxmox1')."""
    state = await _get_client().get_state()
    for n in state.get("nodes", []):
        if n.get("name", "").lower() == node_name.lower():
            mem = n.get("memory", {})
            disk = n.get("disk", {})
            cpu_info = n.get("cpuInfo", {})
            load = n.get("loadAverage", [])
            return (
                f"Node: {n['name']} ({n.get('status', '?')})\n"
                f"Host: {n.get('host', '?')}\n"
                f"CPU: {cpu_info.get('model', '?')} - {cpu_info.get('cores', '?')} cores @ {cpu_info.get('mhz', '?')} MHz\n"
                f"CPU Usage: {_fmt_pct(n.get('cpu', 0) * 100)}\n"
                f"Load Average: {', '.join(str(l) for l in load)}\n"
                f"Memory: {_fmt_bytes(mem.get('used', 0))} / {_fmt_bytes(mem.get('total', 0))} ({_fmt_pct(mem.get('usage', 0))})\n"
                f"Disk: {_fmt_bytes(disk.get('used', 0))} / {_fmt_bytes(disk.get('total', 0))} ({_fmt_pct(disk.get('usage', 0))})\n"
                f"Uptime: {_fmt_uptime(n.get('uptime', 0))}\n"
                f"Kernel: {n.get('kernelVersion', '?')}\n"
                f"PVE Version: {n.get('pveVersion', '?')}\n"
                f"Cluster: {n.get('clusterName', '?')}"
            )
    return f"Node '{node_name}' not found."


@mcp.tool()
async def get_guest_details(name_or_id: str) -> str:
    """Get detailed info for a specific VM or container by name or VMID (e.g. 'DockerVM' or '101')."""
    state = await _get_client().get_state()
    guests = state.get("vms", []) + state.get("containers", [])
    for g in guests:
        if str(g.get("vmid", "")) == str(name_or_id) or g.get("name", "").lower() == name_or_id.lower():
            gtype = "VM (qemu)" if g.get("type") == "qemu" else "LXC Container"
            mem = g.get("memory", {})
            disk = g.get("disk", {})
            disk_str = f"{_fmt_bytes(disk.get('used', 0))} / {_fmt_bytes(disk.get('total', 0))}" if disk.get("total") else "N/A (guest agent not installed)"
            uptime_str = _fmt_uptime(g.get("uptime", 0)) if g.get("uptime") else "-"
            net_in = g.get("netin", 0)
            net_out = g.get("netout", 0)
            return (
                f"Guest: {g.get('name', '?')} (ID: {g.get('vmid', '?')})\n"
                f"Type: {gtype}\n"
                f"Status: {g.get('status', '?')}\n"
                f"Node: {g.get('node', '?')}\n"
                f"CPU: {_fmt_pct(g.get('cpu', 0) * 100)} ({g.get('cpus', '?')} cores)\n"
                f"Memory: {_fmt_bytes(mem.get('used', 0))} / {_fmt_bytes(mem.get('total', 0))} ({_fmt_pct(mem.get('usage', 0))})\n"
                f"Disk: {disk_str}\n"
                f"Uptime: {uptime_str}\n"
                f"Net In: {_fmt_bytes(net_in)}/s  Net Out: {_fmt_bytes(net_out)}/s"
            )
    return f"Guest '{name_or_id}' not found."


@mcp.tool()
async def get_alerts(level: str = "") -> str:
    """Get active alerts. Optionally filter by level ('critical', 'warning', 'info')."""
    alerts = await _get_client().get_alerts_active()
    if level:
        alerts = [a for a in alerts if a.get("level", "").lower() == level.lower()]
    if not alerts:
        return "No active alerts." + (f" (filtered by level={level})" if level else "")
    lines = [f"Active Alerts ({len(alerts)}):"]
    for a in alerts:
        lines.append(
            f"  [{a.get('level', '?').upper():8s}] {a.get('message', '?')}\n"
            f"             Resource: {a.get('resourceName', '?')} ({a.get('resourceId', '?')})\n"
            f"             Type: {a.get('type', '?')}  Value: {a.get('value', '?')}  Threshold: {a.get('threshold', '?')}\n"
            f"             Since: {a.get('startTime', '?')}\n"
            f"             ID: {a.get('id', '?')}\n"
            f"             Acknowledged: {a.get('acknowledged', False)}"
        )
    return "\n".join(lines)


@mcp.tool()
async def get_alert_config() -> str:
    """Get alert configuration: thresholds for CPU, memory, disk for nodes, guests, and storage."""
    config = await _get_client().get_alerts_config()
    lines = ["Alert Configuration:", f"  Enabled: {config.get('enabled', '?')}"]

    for section, label in [("guestDefaults", "Guest Defaults"), ("nodeDefaults", "Node Defaults")]:
        d = config.get(section, {})
        lines.append(f"\n  {label}:")
        for metric in ("cpu", "memory", "disk"):
            m = d.get(metric, {})
            if m:
                lines.append(f"    {metric.upper()}: trigger={m.get('trigger', '?')}%, clear={m.get('clear', '?')}%")
        if "temperature" in d:
            t = d["temperature"]
            lines.append(f"    Temp: trigger={t.get('trigger', '?')}C, clear={t.get('clear', '?')}C")

    sd = config.get("storageDefault", {})
    lines.append(f"\n  Storage Default: trigger={sd.get('trigger', '?')}%, clear={sd.get('clear', '?')}%")

    return "\n".join(lines)


@mcp.tool()
async def get_storage() -> str:
    """Get storage pools across all Proxmox nodes with usage, type, and content info."""
    state = await _get_client().get_state()
    lines = ["Storage Pools:"]
    for n in state.get("nodes", []):
        storages = n.get("storages", [])
        if not storages:
            continue
        lines.append(f"\n  Node: {n['name']}")
        for s in storages:
            total = s.get("total", 0)
            used = s.get("used", 0)
            pct = (used / total * 100) if total else 0
            lines.append(
                f"    {s.get('storage', '?'):16s}  Type: {s.get('type', '?'):8s}  "
                f"Content: {s.get('content', '?')}\n"
                f"{'':20s}  Usage: {_fmt_bytes(used)} / {_fmt_bytes(total)} ({_fmt_pct(pct)})  "
                f"Status: {s.get('status', '?')}"
            )
    if len(lines) == 1:
        lines.append("  No storage data available (storage info may not be included in /api/state)")
    return "\n".join(lines)


@mcp.tool()
async def get_anomalies() -> str:
    """Get AI-detected anomalies in the cluster (unusual CPU, memory, or disk patterns)."""
    data = await _get_client().get_anomalies()
    anomalies = data.get("anomalies", [])
    if not anomalies:
        return f"No anomalies detected. (Total monitored: {data.get('count', 0)})"
    lines = [f"Anomalies ({len(anomalies)}):"]
    for a in anomalies:
        lines.append(
            f"  [{a.get('severity', '?').upper()}] {a.get('description', '?')}\n"
            f"    Resource: {a.get('resource_name', '?')} ({a.get('resource_type', '?')}, {a.get('resource_id', '?')})\n"
            f"    Metric: {a.get('metric', '?')}  Current: {a.get('current_value', '?'):.1f}%\n"
            f"    Baseline: mean={a.get('baseline_mean', 0):.1f}%, stddev={a.get('baseline_std_dev', 0):.2f}\n"
            f"    Z-Score: {a.get('z_score', 0):.2f}"
        )
    return "\n".join(lines)


@mcp.tool()
async def get_health() -> str:
    """Get Pulse server health, version info, and update availability."""
    health = await _get_client().get_health()
    version = await _get_client().get_version()
    update_line = ""
    if version.get("updateAvailable"):
        update_line = f"\nUpdate Available: {version.get('latestVersion', '?')}"
    return (
        f"Health: {health.get('status', '?')}\n"
        f"Version: {version.get('version', '?')} ({version.get('deploymentType', '?')})\n"
        f"Go: {version.get('goVersion', '?')}\n"
        f"Channel: {version.get('channel', '?')}"
        f"{update_line}"
    )


@mcp.tool()
async def get_guests_metadata() -> str:
    """Get metadata (tags, notes, custom URLs) for all monitored VMs and containers."""
    data = await _get_client().get_guests_metadata()
    if not data:
        return "No guest metadata."
    lines = [f"Guest Metadata ({len(data)} entries):"]
    for gid, meta in sorted(data.items()):
        name = meta.get("lastKnownName", "?")
        gtype = "VM" if meta.get("lastKnownType") == "qemu" else "LXC"
        tags = ", ".join(meta.get("tags", [])) or "-"
        url = meta.get("customUrl", "") or "-"
        notes = meta.get("notes") or "-"
        desc = meta.get("description", "") or "-"
        lines.append(f"  {name:16s} ({gtype}, {gid})  Tags: {tags}  URL: {url}  Notes: {notes}  Desc: {desc}")
    return "\n".join(lines)


@mcp.tool()
async def get_system_settings() -> str:
    """Get Pulse system settings: polling intervals, discovery, and other configuration."""
    s = await _get_client().get_system_settings()
    return (
        f"System Settings:\n"
        f"  PVE Polling: {s.get('pvePollingInterval', '?')}s\n"
        f"  PBS Polling: {s.get('pbsPollingInterval', '?')}s\n"
        f"  PMG Polling: {s.get('pmgPollingInterval', '?')}s\n"
        f"  Backup Polling: {s.get('backupPollingEnabled', '?')}\n"
        f"  Connection Timeout: {s.get('connectionTimeout', '?')}s\n"
        f"  Auto Update: {s.get('autoUpdateEnabled', '?')}\n"
        f"  Discovery: {s.get('discoveryEnabled', '?')} (subnet: {s.get('discoverySubnet', '?')})\n"
        f"  Temperature Monitoring: {s.get('temperatureMonitoringEnabled', '?')}\n"
        f"  DNS Cache Timeout: {s.get('dnsCacheTimeout', '?')}s\n"
        f"  Allow Embedding: {s.get('allowEmbedding', '?')}"
    )


# ═══════════════════════════════════════════════════════════════════
#  WRITE TOOLS
# ═══════════════════════════════════════════════════════════════════


@mcp.tool()
async def acknowledge_alert(alert_id: str) -> str:
    """Acknowledge an active alert by its ID (get IDs from get_alerts)."""
    await _get_client().acknowledge_alert(alert_id)
    return f"Alert '{alert_id}' acknowledged."


@mcp.tool()
async def clear_alert(alert_id: str) -> str:
    """Clear an active alert by its ID."""
    await _get_client().clear_alert(alert_id)
    return f"Alert '{alert_id}' cleared."


@mcp.tool()
async def bulk_acknowledge_alerts(alert_ids: str) -> str:
    """Acknowledge multiple alerts at once. Pass alert IDs as comma-separated string."""
    ids = [aid.strip() for aid in alert_ids.split(",") if aid.strip()]
    if not ids:
        return "No alert IDs provided."
    await _get_client().bulk_acknowledge_alerts(ids)
    return f"Acknowledged {len(ids)} alert(s)."


@mcp.tool()
async def update_guest_metadata(
    guest_id: str,
    custom_url: str = "",
    description: str = "",
    tags: str = "",
) -> str:
    """Update metadata for a VM or container. guest_id format: 'Proxmox-NodeName-VMID' (e.g. 'Proxmox-Proxmox2-101'). Tags are comma-separated."""
    payload: dict = {}
    if custom_url:
        payload["customUrl"] = custom_url
    if description:
        payload["description"] = description
    if tags:
        payload["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if not payload:
        return "Nothing to update. Provide at least one of: custom_url, description, tags."
    await _get_client().update_guest_metadata(guest_id, payload)
    return f"Metadata for '{guest_id}' updated: {json.dumps(payload)}"


@mcp.tool()
async def update_alert_config(config_json: str) -> str:
    """Update alert configuration. Pass a JSON string with the fields to update (e.g. thresholds).

    Example: '{"guestDefaults": {"cpu": {"trigger": 90, "clear": 85}}}'
    """
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"
    await _get_client().update_alerts_config(config)
    return f"Alert config updated with: {json.dumps(config)}"


@mcp.tool()
async def update_system_settings(settings_json: str) -> str:
    """Update Pulse system settings. Pass a JSON string with the fields to update.

    Example: '{"pvePollingInterval": 15}'
    """
    try:
        settings = json.loads(settings_json)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"
    await _get_client().update_system_settings(settings)
    return f"System settings updated with: {json.dumps(settings)}"


# ═══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
