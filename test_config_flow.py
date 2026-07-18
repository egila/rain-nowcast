"""Tests for the Rain Nowcast config flow."""

from __future__ import annotations

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rain_nowcast.const import DOMAIN


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """The location-only flow creates one entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Rain Nowcast"
    assert result["data"] == {}


async def test_user_flow_rejects_second_entry(hass: HomeAssistant) -> None:
    """Only one location-based integration entry can exist."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Rain Nowcast",
        data={},
        source=config_entries.SOURCE_USER,
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
