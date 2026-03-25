"""Pulse API client wrapping httpx.AsyncClient."""

import logging
import os
import sys
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class PulseClient:
    """Async HTTP client for the Pulse monitoring API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        skip_tls_verify: bool | None = None,
    ):
        self.base_url = (base_url or os.getenv("PULSE_URL", "")).rstrip("/")
        self.api_token = api_token or os.getenv("PULSE_API_TOKEN", "")
        self.username = username or os.getenv("PULSE_USERNAME", "")
        self.password = password or os.getenv("PULSE_PASSWORD", "")

        if skip_tls_verify is None:
            skip_tls_verify = os.getenv("PULSE_SKIP_TLS_VERIFY", "false").lower() in ("true", "1", "yes")

        if not self.base_url:
            logger.error("PULSE_URL is required")
            sys.exit(1)

        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            verify=not skip_tls_verify,
            timeout=30.0,
            follow_redirects=True,
        )
        self._authenticated = False

    async def _ensure_auth(self) -> None:
        """Authenticate if not already done."""
        if self._authenticated:
            return

        if self.api_token:
            self._http.headers["X-API-Token"] = self.api_token
            self._authenticated = True
            logger.info("Using API token authentication")
            return

        if self.username and self.password:
            resp = await self._http.post(
                "/api/login",
                json={"username": self.username, "password": self.password},
            )
            resp.raise_for_status()
            self._authenticated = True
            logger.info("Authenticated via username/password")
            return

        logger.error("No authentication method configured (set PULSE_API_TOKEN or PULSE_USERNAME + PULSE_PASSWORD)")
        sys.exit(1)

    async def _get(self, path: str) -> Any:
        await self._ensure_auth()
        resp = await self._http.get(path)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, json: Any = None) -> Any:
        await self._ensure_auth()
        resp = await self._http.post(path, json=json)
        resp.raise_for_status()
        return resp.json() if resp.content else {"ok": True}

    async def _put(self, path: str, json: Any = None) -> Any:
        await self._ensure_auth()
        resp = await self._http.put(path, json=json)
        resp.raise_for_status()
        return resp.json() if resp.content else {"ok": True}

    # ── Read endpoints ──────────────────────────────────────────────

    async def get_state(self) -> dict:
        return await self._get("/api/state")

    async def get_health(self) -> dict:
        return await self._get("/api/health")

    async def get_version(self) -> dict:
        return await self._get("/api/version")

    async def get_alerts_active(self) -> list:
        return await self._get("/api/alerts/active")

    async def get_alerts_config(self) -> dict:
        return await self._get("/api/alerts/config")

    async def get_anomalies(self) -> dict:
        return await self._get("/api/ai/intelligence/anomalies")

    async def get_guests_metadata(self) -> dict:
        return await self._get("/api/guests/metadata")

    async def get_system_settings(self) -> dict:
        return await self._get("/api/system/settings")

    # ── Write endpoints ─────────────────────────────────────────────

    async def acknowledge_alert(self, alert_id: str) -> dict:
        return await self._post("/api/alerts/acknowledge", json={"id": alert_id})

    async def clear_alert(self, alert_id: str) -> dict:
        return await self._post("/api/alerts/clear", json={"id": alert_id})

    async def bulk_acknowledge_alerts(self, alert_ids: list[str]) -> dict:
        return await self._post("/api/alerts/bulk/acknowledge", json={"ids": alert_ids})

    async def update_guest_metadata(self, guest_id: str, metadata: dict) -> dict:
        return await self._put(f"/api/guests/metadata/{guest_id}", json=metadata)

    async def update_alerts_config(self, config: dict) -> dict:
        return await self._put("/api/alerts/config", json=config)

    async def update_system_settings(self, settings: dict) -> dict:
        return await self._post("/api/system/settings/update", json=settings)

    async def close(self) -> None:
        await self._http.aclose()
