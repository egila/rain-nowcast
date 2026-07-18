"""Config and options flows for Rain Nowcast."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.core import callback

from .const import (
    CONF_APPROACHING_LEAD_MINUTES,
    CONF_MAX_FORECAST_MINUTES,
    CONF_MIN_MOTION_CONFIDENCE,
    CONF_NEIGHBORHOOD_RADIUS,
    CONF_RAIN_THRESHOLD,
    DOMAIN,
)
from .models import NowcastSettings


class RainNowcastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow that uses Home Assistant's configured location."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> RainNowcastOptionsFlow:
        """Create the options flow for existing entries."""
        return RainNowcastOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Set up the integration using Home Assistant's configured location."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Rain Nowcast", data={})


class RainNowcastOptionsFlow(OptionsFlow):
    """Configure the predictor without recreating the config entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Show and save predictor options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = NowcastSettings()
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_RAIN_THRESHOLD,
                    default=options.get(CONF_RAIN_THRESHOLD, defaults.rain_threshold),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1000.0)),
                vol.Required(
                    CONF_APPROACHING_LEAD_MINUTES,
                    default=options.get(
                        CONF_APPROACHING_LEAD_MINUTES,
                        defaults.approaching_lead_minutes,
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
                vol.Required(
                    CONF_MAX_FORECAST_MINUTES,
                    default=options.get(
                        CONF_MAX_FORECAST_MINUTES, defaults.max_forecast_minutes
                    ),
                ): vol.All(vol.Coerce(int), vol.In(range(5, 61, 5))),
                vol.Required(
                    CONF_MIN_MOTION_CONFIDENCE,
                    default=options.get(
                        CONF_MIN_MOTION_CONFIDENCE,
                        defaults.min_motion_confidence,
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
                vol.Required(
                    CONF_NEIGHBORHOOD_RADIUS,
                    default=options.get(
                        CONF_NEIGHBORHOOD_RADIUS, defaults.neighborhood_radius
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
