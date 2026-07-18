"""Config flow for Rain Nowcast."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN


class RainNowcastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rain Nowcast."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Set up the integration using Home Assistant's configured location."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Rain Nowcast", data={})
