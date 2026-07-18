"""Synthetic tests for global radar-frame motion estimation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from custom_components.rain_nowcast.models import RadarFrame
from custom_components.rain_nowcast.motion import estimate_motion


def _rain_pattern() -> np.ndarray:
    data = np.zeros((128, 128), dtype=np.uint8)
    data[35:46, 40:56] = 125
    data[41:46, 51:63] = 160
    data[64:72, 73:83] = 110
    return data


def _translated(data: np.ndarray, dx: int, dy: int) -> np.ndarray:
    translated = np.zeros_like(data)
    source_row_start = max(0, -dy)
    source_row_end = min(data.shape[0], data.shape[0] - dy)
    source_col_start = max(0, -dx)
    source_col_end = min(data.shape[1], data.shape[1] - dx)
    destination_row_start = max(0, dy)
    destination_col_start = max(0, dx)
    translated[
        destination_row_start : destination_row_start
        + source_row_end
        - source_row_start,
        destination_col_start : destination_col_start
        + source_col_end
        - source_col_start,
    ] = data[source_row_start:source_row_end, source_col_start:source_col_end]
    return translated


def _frame(data: np.ndarray, minutes: int, pixel_size_m: float = 100) -> RadarFrame:
    return RadarFrame(
        timestamp=datetime(2026, 7, 18, tzinfo=UTC) + timedelta(minutes=minutes),
        data=data,
        pixel_size_x_m=pixel_size_m,
        pixel_size_y_m=pixel_size_m,
    )


@pytest.mark.parametrize(
    ("dx", "dy"),
    [
        (6, 0),  # east
        (-6, 0),  # west
        (0, -6),  # north
        (0, 6),  # south
        (5, -4),  # diagonal
        (0, 0),  # stationary
    ],
)
def test_motion_recovers_older_to_newer_sign_convention(dx: int, dy: int) -> None:
    """Columns increase east and rows increase south in the returned motion."""
    older = _frame(_rain_pattern(), 0)
    newer = _frame(_translated(older.data, dx, dy), 5)

    motion = estimate_motion(older, newer)

    assert motion is not None
    assert motion.dx_pixels == dx
    assert motion.dy_pixels == dy
    assert motion.confidence > 0.5


def test_motion_rejects_dry_or_incompatible_or_invalid_frames() -> None:
    """Normal missing-data situations return unavailable motion rather than raising."""
    dry = np.zeros((128, 128), dtype=np.uint8)
    assert estimate_motion(_frame(dry, 0), _frame(dry, 5)) is None

    pattern = _rain_pattern()
    assert estimate_motion(_frame(pattern, 0), _frame(pattern[:64], 5)) is None
    assert estimate_motion(_frame(pattern, 5), _frame(pattern, 0)) is None


def test_motion_rejects_implausible_speed() -> None:
    """A large projected-grid jump cannot become a false weather forecast."""
    older = _frame(_rain_pattern(), 0, pixel_size_m=100_000)
    newer = _frame(_translated(older.data, 1, 0), 5, pixel_size_m=100_000)

    assert estimate_motion(older, newer) is None
