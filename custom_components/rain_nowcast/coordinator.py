"""Coordinator for polling SMHI radar images."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import API_PARAMS, API_URL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .radar import RadarLocationOutsideCoverage, sample_rain_intensity

_LOGGER = logging.getLogger(__name__)


class RainNowcastCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and decode the newest SMHI radar image."""

    def __init__(self, hass: HomeAssistant, latitude: float, longitude: float) -> None:
        """Initialize the coordinator for a fixed Home Assistant location."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=None,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._latitude = latitude
        self._longitude = longitude
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> dict[str, Any]:
        """Download and decode the newest PNG without blocking the event loop."""
        try:
            async with self._session.get(API_URL, params=API_PARAMS) as response:
                response.raise_for_status()
                metadata: Mapping[str, Any] = await response.json()

            image_url, valid_time = _latest_png(metadata)
            async with self._session.get(image_url) as response:
                response.raise_for_status()
                png = await response.read()

            intensity = await self.hass.async_add_executor_job(
                sample_rain_intensity, png, self._latitude, self._longitude
            )
        except RadarLocationOutsideCoverage as err:
            raise UpdateFailed(
                "The configured Home Assistant location is outside SMHI radar coverage"
            ) from err
        except (ClientError, HomeAssistantError, ValueError) as err:
            message = f"Error communicating with SMHI radar API: {err}"
            raise UpdateFailed(message) from err

        return {
            "intensity": intensity,
            "valid_time": valid_time,
            "source_url": image_url,
        }


def _latest_png(metadata: Mapping[str, Any]) -> tuple[str, str | None]:
    """Return the PNG link and observation time from API metadata."""
    for file_info in reversed(metadata.get("lastFiles", [])):
        for image_format in file_info.get("formats", []):
            if image_format.get("key") == "png" and image_format.get("link"):
                return image_format["link"], file_info.get("valid")
    raise ValueError("SMHI response does not contain a PNG image")
