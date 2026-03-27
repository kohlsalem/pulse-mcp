# HTTP/Docker Mode with Basic Auth — Design Spec

**Date:** 2026-03-27
**Status:** Approved

---

## Overview

Add an optional HTTP deployment mode to the pulse-mcp server, packaged as a Docker container. The existing stdio transport is preserved as the default. HTTP mode uses the MCP streamable-http transport with a Basic Auth middleware layer for security.

---

## Architecture

Transport is selected via the `MCP_TRANSPORT` environment variable (`stdio` = default, `streamable-http` = HTTP mode). In HTTP mode, a thin ASGI Basic Auth middleware wraps the FastMCP app before any MCP request is processed.

```
MCP Client (Claude Desktop, Open WebUI, etc.)
    ↓ HTTP + "Authorization: Basic ..." header
BasicAuthMiddleware  ←── MCP_USERNAME / MCP_PASSWORD env vars
    ↓ (credentials valid)
FastMCP (streamable-http transport)
    ↓
PulseClient → Pulse API
```

The MCP tools (all 16) are completely unchanged. Auth is a transport-layer concern only.

---

## Components

### 1. `src/pulse_mcp/server.py` — changes

- Add `BasicAuthMiddleware` (Starlette `BaseHTTPMiddleware` subclass, ~20 lines)
- Modify `main()` to read `MCP_TRANSPORT` and branch:
  - `stdio`: existing `mcp.run(transport="stdio")` — no change
  - `streamable-http`: build the Starlette app via `mcp.streamable_http_app()`, wrap with middleware, run via `uvicorn.run()`
- Validate `MCP_USERNAME`/`MCP_PASSWORD` are set at startup in HTTP mode; exit with clear error if missing
- Use `secrets.compare_digest` for timing-safe credential comparison

**New dependencies used:** `starlette` (already transitive), `uvicorn` (already transitive). No new packages required.

### 2. `Dockerfile`

- Base image: `python:3.12-slim`
- Copy `uv` binary from `ghcr.io/astral-sh/uv:latest`
- `WORKDIR /app`
- Copy `pyproject.toml`, `uv.lock`, then `src/`
- `RUN uv sync --frozen --no-dev`
- Default env: `MCP_TRANSPORT=streamable-http`, `MCP_PORT=8000`
- `EXPOSE 8000`
- `CMD ["uv", "run", "pulse-mcp"]`

### 3. `docker-compose.yml`

Single `pulse-mcp` service. All env vars documented as comments. Includes restart policy.

### 4. `.dockerignore`

Excludes: `.env`, `__pycache__`, `.git`, `*.pyc`, `.python-version`, `docs/`, `README.md`. (Note: `uv.lock` is **not** excluded — it is required by `uv sync --frozen`.)

---

## Environment Variables

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `MCP_TRANSPORT` | `stdio` | No | Transport mode: `stdio` or `streamable-http` |
| `MCP_HOST` | `0.0.0.0` | No | Bind host (HTTP mode only) |
| `MCP_PORT` | `8000` | No | Bind port (HTTP mode only) |
| `MCP_USERNAME` | — | Yes (HTTP) | Basic auth username |
| `MCP_PASSWORD` | — | Yes (HTTP) | Basic auth password |
| `PULSE_URL` | — | Yes | Pulse dashboard base URL |
| `PULSE_API_TOKEN` | — | No* | Pulse API token (*or username+password) |
| `PULSE_USERNAME` | — | No* | Pulse login username |
| `PULSE_PASSWORD` | — | No* | Pulse login password |
| `PULSE_SKIP_TLS_VERIFY` | `false` | No | Disable TLS verification for Pulse API |

---

## Security

- `MCP_USERNAME`/`MCP_PASSWORD` missing in HTTP mode → startup `SystemExit` with clear message
- Wrong credentials → `401 Unauthorized` + `WWW-Authenticate: Basic realm="pulse-mcp"` header
- `secrets.compare_digest` prevents timing attacks
- Credentials never logged

---

## Files Changed / Created

| File | Action |
|------|--------|
| `src/pulse_mcp/server.py` | Modified — add middleware + transport selection |
| `Dockerfile` | Created |
| `docker-compose.yml` | Created |
| `.dockerignore` | Created |

---

## Out of Scope

- TLS termination (handled by reverse proxy)
- Multi-user auth (single credential pair is sufficient)
- Token-based auth (basic auth was explicitly chosen)
