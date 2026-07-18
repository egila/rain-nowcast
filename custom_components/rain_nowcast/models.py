"""Typed models used by the Rain Nowcast predictor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

import numpy as np
from numpy.typing import NDArray

DEFAULT_RAIN_THRESHOLD: Final = 0.1
DEFAULT_APPROACHING_LEAD_MINUTES: Final = 30
DEFAULT_MAX_FORECAST_MINUTES: Final = 60
DEFAULT_MIN_MOTION_CONFIDENCE: Final = 0.35
DEFAULT_NEIGHBORHOOD_RADIUS: Final = 1


@dataclass(frozen=True, slots=True)
class RadarFrame:
    """One decoded SMHI radar frame using raw 8-bit reflectivity values."""

    timestamp: datetime
    data: NDArray[np.uint8]
    pixel_size_x_m: float
    pixel_size_y_m: float


@dataclass(frozen=True, slots=True)
class RadarMotion:
    """Global precipitation motion from an older frame toward a newer frame."""

    dx_pixels: float
    dy_pixels: float
    interval_seconds: float
    confidence: float
    speed_kmh: float
    heading_degrees: float


@dataclass(frozen=True, slots=True)
class RainPrediction:
    """Compact prediction for precipitation reaching the configured location."""

    eta_minutes: int
    eta_at: datetime
    predicted_intensity: float
    forecast_horizon_minutes: int
    motion_confidence: float


@dataclass(frozen=True, slots=True)
class NowcastSettings:
    """User-configurable parameters for the first-generation predictor."""

    rain_threshold: float = DEFAULT_RAIN_THRESHOLD
    approaching_lead_minutes: int = DEFAULT_APPROACHING_LEAD_MINUTES
    max_forecast_minutes: int = DEFAULT_MAX_FORECAST_MINUTES
    min_motion_confidence: float = DEFAULT_MIN_MOTION_CONFIDENCE
    neighborhood_radius: int = DEFAULT_NEIGHBORHOOD_RADIUS


@dataclass(frozen=True, slots=True)
class RainNowcastData:
    """Compact coordinator data exposed to entities and diagnostics."""

    current_intensity: float | None
    radar_timestamp: datetime | None
    radar_timestamp_text: str | None
    source_url: str
    motion: RadarMotion | None
    prediction: RainPrediction | None
    frame_age_minutes: float | None
    cached_frame_count: int
