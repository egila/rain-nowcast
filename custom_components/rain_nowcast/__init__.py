"""Rain Nowcast integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import PLATFORMS
from .coordinator import RainNowcastCoordinator

type RainNowcastConfigEntry = ConfigEntry[RainNowcastCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: RainNowcastConfigEntry
) -> bool:
    """Set up Rain Nowcast from a config entry."""
    coordinator = RainNowcastCoordinator(
        hass,
        config_entry=entry,
        latitude=hass.config.latitude,
        longitude=hass.config.longitude,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        raise

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: RainNowcastConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
