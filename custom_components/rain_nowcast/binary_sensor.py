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
from .models import is_raining


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RainNowcastConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up current-rain and rain-approaching binary sensors."""
    async_add_entities(
        [
            RainingNowBinarySensor(entry.runtime_data),
            RainApproachingBinarySensor(entry.runtime_data),
        ]
    )


class RainingNowBinarySensor(
    CoordinatorEntity[RainNowcastCoordinator], BinarySensorEntity
):
    """Report whether the latest radar sample says it is raining at home."""

    _attr_has_entity_name = True
    _attr_name = "Raining"
    _attr_icon = "mdi:weather-rainy"

    def __init__(self, coordinator: RainNowcastCoordinator) -> None:
        """Initialize the current-rain binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_rain_now"
        self._attr_device_info = _device_info()

    @property
    def is_on(self) -> bool | None:
        """Return the current radar rain state, or unavailable without a sample."""
        data = self.coordinator.data
        if data is None or data.current_intensity is None:
            return None
        return is_raining(
            data.current_intensity, self.coordinator.settings.rain_threshold
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the current sample and threshold used for the binary state."""
        data = self.coordinator.data
        if data is None:
            return {}
        return {
            "rain_intensity": data.current_intensity,
            "rain_threshold": self.coordinator.settings.rain_threshold,
            "radar_observation_time": data.radar_timestamp_text,
        }


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
        self._attr_device_info = _device_info()

    @property
    def is_on(self) -> bool | None:
        """Return true only for a sufficiently confident near-term arrival."""
        data = self.coordinator.data
        if data is None or data.prediction is None:
            return None
        prediction = data.prediction
        settings = self.coordinator.settings
        if is_raining(data.current_intensity, settings.rain_threshold):
            return False
        return (
            0 < prediction.eta_minutes <= settings.approaching_lead_minutes
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


def _device_info() -> DeviceInfo:
    """Return the shared integration device metadata."""
    return DeviceInfo(
        identifiers={(DOMAIN, DOMAIN)},
        name="Rain Nowcast",
        manufacturer="Rain Nowcast",
        model="Sweden radar composite",
    )
