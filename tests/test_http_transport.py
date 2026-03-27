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
    response = client.get("/mcp", headers={"Authorization": _basic_header("testuser", "testpass")})
    assert response.status_code != 401


def test_missing_mcp_username_raises():
    env = {"MCP_PASSWORD": "testpass", "PULSE_URL": "http://fake", "PULSE_API_TOKEN": "fake"}
    with patch.dict(os.environ, env, clear=False):
        os.environ.pop("MCP_USERNAME", None)
        from pulse_mcp.server import make_http_app
        with pytest.raises(SystemExit):
            make_http_app()
