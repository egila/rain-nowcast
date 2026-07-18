"""Diagnostics support for Rain Nowcast."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import RainNowcastConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RainNowcastConfigEntry
) -> dict[str, Any]:
    """Return compact, location-free predictor diagnostics.

    Radar arrays and the configured home coordinates are deliberately omitted.
    """
    coordinator = entry.runtime_data
    data = coordinator.data
    if data is None:
        return {"cached_frame_count": len(coordinator.frame_cache), "data": None}

    motion = data.motion
    prediction = data.prediction
    return {
        "cached_frame_count": len(coordinator.frame_cache),
        "cached_timestamps": [
            frame.timestamp.isoformat() for frame in coordinator.frame_cache.frames
        ],
        "frame_age_minutes": data.frame_age_minutes,
        "motion": (
            {
                "dx_pixels": motion.dx_pixels,
                "dy_pixels": motion.dy_pixels,
                "interval_seconds": motion.interval_seconds,
                "confidence": motion.confidence,
                "speed_kmh": motion.speed_kmh,
                "heading_degrees": motion.heading_degrees,
            }
            if motion is not None
            else None
        ),
        "prediction": (
            {
                "eta_minutes": prediction.eta_minutes,
                "eta_at": prediction.eta_at.isoformat(),
                "predicted_intensity": prediction.predicted_intensity,
                "forecast_horizon_minutes": prediction.forecast_horizon_minutes,
                "motion_confidence": prediction.motion_confidence,
            }
            if prediction is not None
            else None
        ),
    }
