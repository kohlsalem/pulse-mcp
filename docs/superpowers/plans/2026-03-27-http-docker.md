# HTTP/Docker Mode with Basic Auth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional HTTP deployment mode to pulse-mcp with Basic Auth, packaged as a Docker container, while keeping stdio as the default transport.

**Architecture:** Transport is selected via `MCP_TRANSPORT` env var. In `streamable-http` mode, a Starlette `BaseHTTPMiddleware` subclass validates the `Authorization: Basic` header before any MCP request is processed. The FastMCP app is obtained via `mcp.streamable_http_app()` and served with uvicorn directly (instead of `mcp.run()`).

**Tech Stack:** Python 3.12, FastMCP (mcp[cli]>=1.26.0), Starlette (transitive), Uvicorn (transitive), Docker with uv.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/pulse_mcp/server.py` | Modify | Add `BasicAuthMiddleware`, update `main()` for transport branching |
| `Dockerfile` | Create | Container image: uv-based Python 3.12 slim, exposes port 8000 |
| `docker-compose.yml` | Create | Service definition with all env vars documented |
| `.dockerignore` | Create | Exclude irrelevant files from build context |
| `.env.example` | Modify | Add `MCP_TRANSPORT`, `MCP_HOST`, `MCP_PORT`, `MCP_USERNAME`, `MCP_PASSWORD` |

---

## Task 1: Add BasicAuthMiddleware and HTTP transport to server.py

**Files:**
- Modify: `src/pulse_mcp/server.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_http_transport.py`:

```python
"""Tests for HTTP transport mode with Basic Auth."""
import base64
import os
import pytest
from unittest.mock import patch
from starlette.testclient import TestClient


def _basic_header(username: str, password: str) -> str:
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {creds}"


@pytest.fixture
def http_app():
    """Return the FastMCP Starlette app wrapped with BasicAuthMiddleware."""
    with patch.dict(os.environ, {
        "MCP_USERNAME": "testuser",
        "MCP_PASSWORD": "testpass",
        "PULSE_URL": "http://fake-pulse",
        "PULSE_API_TOKEN": "fake-token",
    }):
        # Import inside fixture so env vars are set before module-level code runs
        from pulse_mcp.server import make_http_app
        return make_http_app()


def test_no_auth_returns_401(http_app):
    client = TestClient(http_app, raise_server_exceptions=False)
    response = client.get("/mcp")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="pulse-mcp"'


def test_wrong_password_returns_401(http_app):
    client = TestClient(http_app, raise_server_exceptions=False)
    response = client.get("/mcp", headers={"Authorization": _basic_header("testuser", "wrong")})
    assert response.status_code == 401


def test_wrong_username_returns_401(http_app):
    client = TestClient(http_app, raise_server_exceptions=False)
    response = client.get("/mcp", headers={"Authorization": _basic_header("wrong", "testpass")})
    assert response.status_code == 401


def test_valid_credentials_pass_through(http_app):
    client = TestClient(http_app, raise_server_exceptions=False)
    # A valid auth header should NOT return 401 (MCP may return 4xx for other reasons,
    # but the auth layer should pass it through)
    response = client.get("/mcp", headers={"Authorization": _basic_header("testuser", "testpass")})
    assert response.status_code != 401


def test_missing_mcp_username_raises():
    env = {"MCP_PASSWORD": "testpass", "PULSE_URL": "http://fake", "PULSE_API_TOKEN": "fake"}
    # Ensure MCP_USERNAME is absent
    with patch.dict(os.environ, env, clear=False):
        os.environ.pop("MCP_USERNAME", None)
        from pulse_mcp.server import make_http_app
        with pytest.raises(SystemExit):
            make_http_app()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/D054904/kohlsalem/pulse-mcp
uv run pytest tests/test_http_transport.py -v 2>&1 | head -30
```

Expected: `ImportError` or `AttributeError: module 'pulse_mcp.server' has no attribute 'make_http_app'`

- [ ] **Step 3: Implement BasicAuthMiddleware and make_http_app() in server.py**

Replace the `main()` function and add the middleware. The complete additions to `src/pulse_mcp/server.py` — add these imports at the top (after existing imports):

```python
import base64
import os
import secrets

import uvicorn
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
```

Add the middleware class and `make_http_app()` function before `main()` (replacing the existing `def main():`):

```python
class BasicAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, username: str, password: str) -> None:
        super().__init__(app)
        self._username = username
        self._password = password

    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return Response(
                "Unauthorized",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="pulse-mcp"'},
            )
        try:
            decoded = base64.b64decode(auth[6:]).decode()
            username, _, password = decoded.partition(":")
        except Exception:
            return Response(
                "Unauthorized",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="pulse-mcp"'},
            )
        valid = secrets.compare_digest(username, self._username) and secrets.compare_digest(
            password, self._password
        )
        if not valid:
            return Response(
                "Unauthorized",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="pulse-mcp"'},
            )
        return await call_next(request)


def make_http_app():
    """Build the Starlette app with BasicAuthMiddleware. Exits if credentials not configured."""
    username = os.environ.get("MCP_USERNAME", "")
    password = os.environ.get("MCP_PASSWORD", "")
    if not username or not password:
        logger.error("MCP_USERNAME and MCP_PASSWORD must be set when using HTTP transport")
        raise SystemExit(1)
    app = mcp.streamable_http_app()
    return BasicAuthMiddleware(app, username=username, password=password)


def main():
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        host = os.environ.get("MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("MCP_PORT", "8000"))
        app = make_http_app()
        uvicorn.run(app, host=host, port=port)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_http_transport.py -v
```

Expected output:
```
tests/test_http_transport.py::test_no_auth_returns_401 PASSED
tests/test_http_transport.py::test_wrong_password_returns_401 PASSED
tests/test_http_transport.py::test_wrong_username_returns_401 PASSED
tests/test_http_transport.py::test_valid_credentials_pass_through PASSED
tests/test_http_transport.py::test_missing_mcp_username_raises PASSED
```

- [ ] **Step 5: Commit**

```bash
git add src/pulse_mcp/server.py tests/test_http_transport.py
git commit -m "FEAT: add HTTP streamable-http transport with Basic Auth middleware"
```

---

## Task 2: Update .env.example with new HTTP vars

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add HTTP transport variables to .env.example**

The new `.env.example` should look like this (full file):

```ini
# Pulse MCP Server Configuration
# At least one auth method is required: API token (recommended) or username/password

# Required: Pulse instance URL
PULSE_URL=https://pulse.kohlsalem.com

# Option 1: API Token (recommended - create in Pulse Settings > Security > API Tokens)
PULSE_API_TOKEN=

# Option 2: Username/Password (fallback if no token)
PULSE_USERNAME=admin
PULSE_PASSWORD=admin

# Optional: Skip TLS verification for self-signed certs (default: false)
PULSE_SKIP_TLS_VERIFY=true

# --- HTTP / Docker mode ---
# Set MCP_TRANSPORT=streamable-http to run as an HTTP server instead of stdio
MCP_TRANSPORT=stdio

# Host and port for HTTP mode (defaults shown)
MCP_HOST=0.0.0.0
MCP_PORT=8000

# Required when MCP_TRANSPORT=streamable-http: credentials for Basic Auth
MCP_USERNAME=
MCP_PASSWORD=
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "DOC: add HTTP transport env vars to .env.example"
```

---

## Task 3: Create Dockerfile

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies (cached layer — only rebuilds when lock file changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ src/

# Default to HTTP transport
ENV MCP_TRANSPORT=streamable-http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000

EXPOSE 8000

CMD ["uv", "run", "pulse-mcp"]
```

- [ ] **Step 2: Verify image builds**

```bash
docker build -t pulse-mcp:test .
```

Expected: `Successfully built <id>` with no errors.

- [ ] **Step 3: Verify container starts and shows auth error without credentials**

```bash
docker run --rm \
  -e PULSE_URL=http://fake \
  -e PULSE_API_TOKEN=fake \
  pulse-mcp:test 2>&1 | head -5
```

Expected output contains: `MCP_USERNAME and MCP_PASSWORD must be set`

- [ ] **Step 4: Commit**

```bash
git add Dockerfile
git commit -m "FEAT: add Dockerfile for HTTP/Docker deployment mode"
```

---

## Task 4: Create docker-compose.yml and .dockerignore

**Files:**
- Create: `docker-compose.yml`
- Create: `.dockerignore`

- [ ] **Step 1: Create docker-compose.yml**

```yaml
services:
  pulse-mcp:
    build: .
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      # --- Pulse connection (required) ---
      PULSE_URL: "https://pulse.example.com"
      # Option 1: API token (recommended)
      PULSE_API_TOKEN: ""
      # Option 2: username/password (if no token)
      # PULSE_USERNAME: "admin"
      # PULSE_PASSWORD: "admin"
      # Skip TLS verification for self-signed certs
      PULSE_SKIP_TLS_VERIFY: "false"

      # --- HTTP transport (required) ---
      MCP_TRANSPORT: "streamable-http"
      MCP_HOST: "0.0.0.0"
      MCP_PORT: "8000"
      # Basic Auth credentials — set these before running
      MCP_USERNAME: ""
      MCP_PASSWORD: ""
```

- [ ] **Step 2: Create .dockerignore**

```
.env
.git
.gitignore
.python-version
__pycache__
*.pyc
*.pyo
docs/
README.md
tests/
```

- [ ] **Step 3: Verify compose build**

```bash
docker compose build
```

Expected: builds successfully.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml .dockerignore
git commit -m "FEAT: add docker-compose.yml and .dockerignore"
```

---

## Task 5: Smoke test end-to-end

- [ ] **Step 1: Run the full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 2: Verify stdio mode still works**

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' | \
  PULSE_URL=http://fake PULSE_API_TOKEN=fake uv run pulse-mcp
```

Expected: JSON response starting with `{"jsonrpc":"2.0"` — no crash, no HTTP server started.

- [ ] **Step 3: Verify HTTP mode rejects bad credentials**

```bash
docker run --rm -d --name pulse-mcp-test \
  -e PULSE_URL=http://fake \
  -e PULSE_API_TOKEN=fake \
  -e MCP_USERNAME=user \
  -e MCP_PASSWORD=pass \
  -p 8000:8000 \
  pulse-mcp:test

sleep 2

curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/mcp
```

Expected: `401`

- [ ] **Step 4: Verify HTTP mode accepts valid credentials**

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -u user:pass \
  http://localhost:8000/mcp
```

Expected: anything other than `401` (likely `405` or `200` from the MCP endpoint).

- [ ] **Step 5: Stop the test container**

```bash
docker stop pulse-mcp-test
```

- [ ] **Step 6: Final commit if any loose changes**

```bash
git status
# If clean, nothing to do. If there are any remaining changes:
# git add <files> && git commit -m "CHORE: final cleanup"
```
