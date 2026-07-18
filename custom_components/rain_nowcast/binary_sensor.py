"""Binary sensor platform for Rain Nowcast."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RainNowcastConfigEntry
from .const import DOMAIN
from .coordinator import RainNowcastCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RainNowcastConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the rain-approaching binary sensor."""
    async_add_entities([RainApproachingBinarySensor(entry.runtime_data)])


class RainApproachingBinarySensor(
    CoordinatorEntity[RainNowcastCoordinator], BinarySensorEntity
):
    """Report whether rain is expected within the configured lead time."""

    _attr_has_entity_name = True
    _attr_name = "Rain approaching"
    _attr_icon = "mdi:weather-rainy"

    def __init__(self, coordinator: RainNowcastCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_rain_approaching"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name="Rain Nowcast",
            manufacturer="Rain Nowcast",
            model="Sweden radar composite",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true only for a sufficiently confident near-term arrival."""
        data = self.coordinator.data
        if data is None or data.prediction is None:
            return None
        prediction = data.prediction
        settings = self.coordinator.settings
        return (
            prediction.eta_minutes <= settings.approaching_lead_minutes
            and prediction.predicted_intensity >= settings.rain_threshold
            and prediction.motion_confidence >= settings.min_motion_confidence
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the compact prediction behind the binary state."""
        data = self.coordinator.data
        if data is None or data.prediction is None:
            return {}
        prediction = data.prediction
        return {
            "eta_minutes": prediction.eta_minutes,
            "predicted_intensity": prediction.predicted_intensity,
            "motion_confidence": prediction.motion_confidence,
            "radar_observation_time": data.radar_timestamp_text,
        }
