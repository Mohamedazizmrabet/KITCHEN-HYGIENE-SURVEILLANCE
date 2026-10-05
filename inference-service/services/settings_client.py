"""
services/settings_client.py — HTTP client for Laravel settings API.

Pulls active model selection, confidence threshold, and enabled
PPE classes from the Laravel backend so they can be applied live
without restarting the inference service.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

import config

logger = logging.getLogger(__name__)

# How long to wait for Laravel before giving up (seconds)
_TIMEOUT = 5.0


class SettingsClient:
    """Thin async HTTP client for the Laravel /api/settings endpoint."""

    def __init__(self, base_url: str = "") -> None:
        self._base_url = base_url or config.LARAVEL_BASE_URL

    async def fetch_settings(self) -> Optional[Dict[str, Any]]:
        """Retrieve current application settings from Laravel.

        Returns:
            Settings dict on success, or None on network/server error.
        """
        url = f"{self._base_url}/api/settings"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                logger.debug(f"[SettingsClient] Fetched settings: {data}")
                return data
        except httpx.ConnectError:
            logger.warning(
                f"[SettingsClient] Cannot reach Laravel at {url}. "
                f"Using local defaults."
            )
        except httpx.HTTPStatusError as exc:
            logger.warning(
                f"[SettingsClient] Settings endpoint returned {exc.response.status_code}."
            )
        except Exception as exc:
            logger.error(f"[SettingsClient] Unexpected error: {exc}")

        return None

    async def push_violation(self, violation_payload: Dict[str, Any]) -> bool:
        """Push a detected violation event to Laravel for persistence.

        Args:
            violation_payload: Dict matching the violations table schema.

        Returns:
            True if successfully received by Laravel, False otherwise.
        """
        url = f"{self._base_url}/api/violations"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(url, json=violation_payload)
                response.raise_for_status()
                return True
        except Exception as exc:
            logger.warning(f"[SettingsClient] Failed to push violation: {exc}")
            return False
