"""Tests for deterministic frame projection and rain-arrival calculation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np

from custom_components.rain_nowcast.models import RadarFrame, RadarMotion
from custom_components.rain_nowcast.predictor import (
    extrapolate_frame,
    predict_rain_arrival,
)


def _frame(data: np.ndarray) -> RadarFrame:
    return RadarFrame(
        timestamp=datetime(2026, 7, 18, tzinfo=UTC),
        data=data,
        pixel_size_x_m=100,
        pixel_size_y_m=100,
    )


def _motion(dx: float = 1, dy: float = 0, confidence: float = 0.9) -> RadarMotion:
    return RadarMotion(
        dx_pixels=dx,
        dy_pixels=dy,
        interval_seconds=300,
        confidence=confidence,
        speed_kmh=1,
        heading_degrees=90,
    )


def test_extrapolation_projects_each_requested_horizon_without_wrapping() -> None:
    """A five-minute update displacement scales linearly through one hour."""
    data = np.zeros((20, 30), dtype=np.uint8)
    data[10, 2] = 120
    frame = _frame(data)

    for minutes, column in ((5, 3), (15, 5), (30, 8), (60, 14)):
        projected = extrapolate_frame(frame, _motion(), timedelta(minutes=minutes))
        assert projected[10, column] == 120
        assert projected.min() >= 0

    data[10, -1] = 120
    boundary = extrapolate_frame(_frame(data), _motion(), timedelta(minutes=5))
    assert boundary[10, 0] == 0


def test_extrapolation_supports_fractional_displacements() -> None:
    """Bilinear projection keeps fractional movement deterministic and non-negative."""
    data = np.zeros((10, 10), dtype=np.uint8)
    data[5, 2] = 120
    projected = extrapolate_frame(_frame(data), _motion(dx=0.5), timedelta(minutes=5))

    assert projected[5, 2] == 60
    assert projected[5, 3] == 60
    assert projected.min() >= 0


def test_eta_handles_current_arrival_horizon_and_no_arrival() -> None:
    """ETA uses 5-minute steps and leaves no-arrival forecasts unavailable."""
    current = np.zeros((20, 30), dtype=np.uint8)
    current[10, 20] = 120
    assert (
        predict_rain_arrival(_frame(current), _motion(), 10, 20, 0.1, 60, 0).eta_minutes
        == 0
    )

    arriving = np.zeros((20, 30), dtype=np.uint8)
    arriving[10, 14] = 120
    prediction = predict_rain_arrival(_frame(arriving), _motion(), 10, 20, 0.1, 60, 0)
    assert prediction is not None
    assert prediction.eta_minutes == 30

    moving_away = predict_rain_arrival(
        _frame(arriving), _motion(dx=-1), 10, 20, 0.1, 60, 0
    )
    assert moving_away is None
    assert (
        predict_rain_arrival(
            _frame(arriving), _motion(confidence=0), 10, 20, 0.1, 60, 0
        )
        is None
    )


def test_eta_never_treats_no_echo_as_rain_with_a_zero_threshold() -> None:
    """A zero user threshold must not turn dry radar samples into an arrival."""
    dry = np.zeros((20, 30), dtype=np.uint8)

    assert predict_rain_arrival(_frame(dry), _motion(), 10, 20, 0.0, 60, 0) is None


def test_eta_uses_the_configured_neighborhood() -> None:
    """A nearby cell can trigger a future robust arrival when it moves homeward."""
    data = np.zeros((20, 30), dtype=np.uint8)
    data[9, 20] = 120

    assert predict_rain_arrival(_frame(data), _motion(), 10, 20, 0.1, 60, 0) is None
    prediction = predict_rain_arrival(_frame(data), _motion(), 10, 20, 0.1, 60, 1)
    assert prediction is not None
    assert prediction.eta_minutes == 5


def test_stationary_nearby_rain_does_not_become_an_arrival() -> None:
    """A wet nearby cell must not produce a false ETA without movement."""
    data = np.zeros((20, 30), dtype=np.uint8)
    data[9, 20] = 120

    assert predict_rain_arrival(_frame(data), _motion(dx=0), 10, 20, 0.1, 60, 1) is None
