"""Tests for compact Rain Nowcast entity behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from homeassistant.const import DEGREE, EntityCategory, UnitOfSpeed, UnitOfTime

from custom_components.rain_nowcast import binary_sensor, sensor
from custom_components.rain_nowcast.binary_sensor import RainApproachingBinarySensor
from custom_components.rain_nowcast.models import (
    NowcastSettings,
    RadarMotion,
    RainNowcastData,
    RainPrediction,
)
from custom_components.rain_nowcast.sensor import (
    DIAGNOSTIC_DESCRIPTIONS,
    RainDiagnosticSensor,
    RainEtaSensor,
    RainIntensitySensor,
)


def _data(prediction: RainPrediction | None = None) -> RainNowcastData:
    motion = RadarMotion(
        dx_pixels=4,
        dy_pixels=-2,
        interval_seconds=300,
        confidence=0.8,
        speed_kmh=5.4,
        heading_degrees=63.4,
    )
    return RainNowcastData(
        current_intensity=0.63,
        radar_timestamp=datetime(2026, 7, 18, tzinfo=UTC),
        radar_timestamp_text="2026-07-18 12:00",
        source_url="https://example.invalid/radar.tif",
        motion=motion,
        prediction=prediction,
        frame_age_minutes=4.2,
        cached_frame_count=2,
    )


def _coordinator(data: RainNowcastData | None) -> SimpleNamespace:
    return SimpleNamespace(data=data, settings=NowcastSettings())


def test_entity_values_unique_ids_and_diagnostic_units() -> None:
    """Current and diagnostic entities use stable recorder-friendly values."""
    coordinator = _coordinator(_data())
    intensity = RainIntensitySensor(coordinator)
    diagnostics = [
        RainDiagnosticSensor(coordinator, description)
        for description in DIAGNOSTIC_DESCRIPTIONS
    ]

    assert intensity.unique_id == "rain_nowcast_rain_intensity"
    assert intensity.native_value == 0.63
    assert all(
        sensor.entity_category is EntityCategory.DIAGNOSTIC for sensor in diagnostics
    )
    assert diagnostics[3].native_unit_of_measurement == UnitOfSpeed.KILOMETERS_PER_HOUR
    assert diagnostics[4].native_unit_of_measurement == DEGREE
    assert diagnostics[5].native_unit_of_measurement == UnitOfTime.MINUTES


async def test_platform_setup_creates_all_entities() -> None:
    """Sensor platforms create the current, ETA, diagnostic, and binary entities."""
    coordinator = _coordinator(_data())
    entry = SimpleNamespace(runtime_data=coordinator)
    sensors: list[object] = []
    binary_sensors: list[object] = []

    await sensor.async_setup_entry(None, entry, sensors.extend)
    await binary_sensor.async_setup_entry(None, entry, binary_sensors.extend)

    assert len(sensors) == 8
    assert sensors[0].unique_id == "rain_nowcast_rain_intensity"
    assert len(binary_sensors) == 1
    assert binary_sensors[0].unique_id == "rain_nowcast_rain_approaching"


def test_eta_and_approaching_are_unavailable_until_a_prediction_exists() -> None:
    """Startup with only one radar frame does not produce an invented arrival."""
    coordinator = _coordinator(None)
    assert RainEtaSensor(coordinator).native_value is None
    assert RainApproachingBinarySensor(coordinator).is_on is None


def test_eta_and_approaching_use_prediction_and_configured_thresholds() -> None:
    """A confident near-term forecast turns the binary sensor on."""
    timestamp = datetime(2026, 7, 18, tzinfo=UTC)
    prediction = RainPrediction(
        eta_minutes=20,
        eta_at=timestamp + timedelta(minutes=20),
        predicted_intensity=0.4,
        forecast_horizon_minutes=20,
        motion_confidence=0.8,
    )
    coordinator = _coordinator(_data(prediction))

    eta = RainEtaSensor(coordinator)
    approaching = RainApproachingBinarySensor(coordinator)
    assert eta.native_value == prediction.eta_at
    assert eta.extra_state_attributes["eta_minutes"] == 20
    assert approaching.is_on is True
