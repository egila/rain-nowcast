"""Sensor platform for Rain Nowcast."""


from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfVolumetricFlux
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RainNowcastConfigEntry
from .const import ATTRIBUTION, DOMAIN
from .coordinator import RainNowcastCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RainNowcastConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the rain intensity sensor."""
    async_add_entities([RainIntensitySensor(entry.runtime_data)])




class RainIntensitySensor(CoordinatorEntity[RainNowcastCoordinator], SensorEntity):
    """Represent the current precipitation intensity at Home Assistant's location."""


    _attr_has_entity_name = True
    _attr_name = "Rain intensity"
    _attr_native_unit_of_measurement = UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR
    _attr_device_class = SensorDeviceClass.PRECIPITATION_INTENSITY
    _attr_icon = "mdi:weather-pouring"


    def __init__(self, coordinator: RainNowcastCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_rain_intensity"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name="Rain Nowcast",
            manufacturer="Rain Nowcast",
            model="Sweden radar composite",
        )


    @property
    def native_value(self) -> float | None:
        """Return precipitation intensity in mm/h."""
        return self.coordinator.data["intensity"]


    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return source and radar observation details."""
        return {
            "attribution": ATTRIBUTION,
            "radar_observation_time": self.coordinator.data.get("valid_time"),
            "source_url": self.coordinator.data.get("source_url"),
        }
