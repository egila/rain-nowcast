"""Sensor platform for Rain Nowcast."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfSpeed,
    UnitOfTime,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RainNowcastConfigEntry
from .const import ATTRIBUTION, DOMAIN
from .coordinator import RainNowcastCoordinator
from .models import RainNowcastData

INTENSITY_DESCRIPTION = SensorEntityDescription(
    key="rain_intensity",
    name="Rain intensity",
    native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
    device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
    icon="mdi:weather-pouring",
)
ETA_DESCRIPTION = SensorEntityDescription(
    key="rain_eta",
    name="Rain ETA",
    device_class=SensorDeviceClass.TIMESTAMP,
    icon="mdi:clock-outline",
)
DIAGNOSTIC_DESCRIPTIONS = (
    SensorEntityDescription(
        key="rain_confidence",
        name="Rain confidence",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:percent-outline",
    ),
    SensorEntityDescription(
        key="radar_motion_x",
        name="Radar motion X",
        native_unit_of_measurement="px",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:arrow-right",
    ),
    SensorEntityDescription(
        key="radar_motion_y",
        name="Radar motion Y",
        native_unit_of_measurement="px",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:arrow-down",
    ),
    SensorEntityDescription(
        key="radar_speed",
        name="Radar speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="radar_heading",
        name="Radar heading",
        native_unit_of_measurement=DEGREE,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:compass-outline",
    ),
    SensorEntityDescription(
        key="radar_frame_age",
        name="Radar frame age",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:clock-alert-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RainNowcastConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Rain Nowcast sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            RainIntensitySensor(coordinator),
            RainEtaSensor(coordinator),
            *(
                RainDiagnosticSensor(coordinator, description)
                for description in DIAGNOSTIC_DESCRIPTIONS
            ),
        ]
    )


class RainNowcastSensorBase(CoordinatorEntity[RainNowcastCoordinator], SensorEntity):
    """Common device and unique-ID handling for Rain Nowcast sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RainNowcastCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a sensor sharing the integration device."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{description.key}"
        self._attr_device_info = _device_info()

    @property
    def _data(self) -> RainNowcastData | None:
        """Return coordinator data when the first refresh has completed."""
        return self.coordinator.data


class RainIntensitySensor(RainNowcastSensorBase):
    """Represent current precipitation intensity at Home Assistant's location."""

    def __init__(self, coordinator: RainNowcastCoordinator) -> None:
        """Initialize the current-rain sensor."""
        super().__init__(coordinator, INTENSITY_DESCRIPTION)

    @property
    def native_value(self) -> float | None:
        """Return precipitation intensity in mm/h."""
        return self._data.current_intensity if self._data else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return source and radar observation details."""
        data = self._data
        if data is None:
            return {"attribution": ATTRIBUTION}
        return {
            "attribution": ATTRIBUTION,
            "radar_observation_time": data.radar_timestamp_text,
            "source_url": data.source_url,
        }


class RainEtaSensor(RainNowcastSensorBase):
    """Represent the predicted timestamp for rain reaching home."""

    def __init__(self, coordinator: RainNowcastCoordinator) -> None:
        """Initialize the rain-arrival sensor."""
        super().__init__(coordinator, ETA_DESCRIPTION)

    @property
    def native_value(self) -> Any:
        """Return the arrival timestamp, or unavailable when no ETA is known."""
        if self._data is None or self._data.prediction is None:
            return None
        return self._data.prediction.eta_at

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return compact inputs used to produce the ETA."""
        data = self._data
        if data is None or data.prediction is None:
            return {}
        prediction = data.prediction
        return {
            "eta_minutes": prediction.eta_minutes,
            "predicted_intensity": prediction.predicted_intensity,
            "forecast_horizon_minutes": prediction.forecast_horizon_minutes,
            "radar_observation_time": data.radar_timestamp_text,
            "motion_confidence": prediction.motion_confidence,
        }


class RainDiagnosticSensor(RainNowcastSensorBase):
    """Expose compact motion and freshness diagnostics."""

    def __init__(
        self,
        coordinator: RainNowcastCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize one diagnostic sensor."""
        super().__init__(coordinator, description)

    @property
    def native_value(self) -> float | None:
        """Return the matching motion or freshness diagnostic."""
        data = self._data
        if data is None:
            return None
        if self.entity_description.key == "radar_frame_age":
            return data.frame_age_minutes
        if data.motion is None:
            return None
        values = {
            "rain_confidence": data.motion.confidence * 100,
            "radar_motion_x": data.motion.dx_pixels,
            "radar_motion_y": data.motion.dy_pixels,
            "radar_speed": data.motion.speed_kmh,
            "radar_heading": data.motion.heading_degrees,
        }
        value = values.get(self.entity_description.key)
        return round(value, 1) if value is not None else None


def _device_info() -> DeviceInfo:
    """Return the shared integration device metadata."""
    return DeviceInfo(
        identifiers={(DOMAIN, DOMAIN)},
        name="Rain Nowcast",
        manufacturer="Rain Nowcast",
        model="Sweden radar composite",
    )
