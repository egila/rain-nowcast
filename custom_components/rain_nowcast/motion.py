"""Pure NumPy global-motion estimation for SMHI radar frames."""

from __future__ import annotations

from math import atan2, ceil, degrees, hypot, log1p
from typing import Final

import numpy as np
from numpy.typing import NDArray

from .models import RadarFrame, RadarMotion
from .radar import MINIMUM_PRECIPITATION_DBZ, SMHI_GAIN, SMHI_OFFSET

MAX_ANALYSIS_DIMENSION: Final = 256
MIN_WET_PIXELS: Final = 24
MAX_SPEED_KMH: Final = 180.0


def estimate_motion(older: RadarFrame, newer: RadarFrame) -> RadarMotion | None:
    """Estimate older-to-newer translation using phase correlation.

    The returned ``dx_pixels`` moves east (increasing array column), while
    ``dy_pixels`` moves south (increasing array row). SMHI's GeoTIFF rows are
    north-to-south, so this maps directly to geographic heading.
    """
    if not _frames_compatible(older, newer):
        return None

    interval_seconds = (newer.timestamp - older.timestamp).total_seconds()
    if interval_seconds <= 0 or interval_seconds > 1_800:
        return None

    older_data, newer_data, scale = _prepare_frames(older.data, newer.data)
    wet_pixels = min(np.count_nonzero(older_data), np.count_nonzero(newer_data))
    if wet_pixels < MIN_WET_PIXELS:
        return None

    dy_small, dx_small, peak_ratio = _phase_correlation_shift(older_data, newer_data)
    dx_pixels = dx_small * scale
    dy_pixels = dy_small * scale

    speed_kmh = _speed_kmh(
        dx_pixels,
        dy_pixels,
        interval_seconds,
        newer.pixel_size_x_m,
        newer.pixel_size_y_m,
    )
    if speed_kmh > MAX_SPEED_KMH:
        return None

    overlap = _wet_overlap(older_data, newer_data, int(dy_small), int(dx_small))
    confidence = min(1.0, log1p(peak_ratio) / log1p(20.0)) * overlap
    if confidence <= 0.0:
        return None

    return RadarMotion(
        dx_pixels=round(dx_pixels, 3),
        dy_pixels=round(dy_pixels, 3),
        interval_seconds=interval_seconds,
        confidence=round(confidence, 3),
        speed_kmh=round(speed_kmh, 2),
        heading_degrees=round(_heading_degrees(dx_pixels, dy_pixels), 1),
    )


def _frames_compatible(older: RadarFrame, newer: RadarFrame) -> bool:
    """Check that two cached grids can be compared safely."""
    return (
        older.data.shape == newer.data.shape
        and np.isclose(older.pixel_size_x_m, newer.pixel_size_x_m)
        and np.isclose(older.pixel_size_y_m, newer.pixel_size_y_m)
    )


def _prepare_frames(
    older: NDArray[np.uint8], newer: NDArray[np.uint8]
) -> tuple[NDArray[np.float32], NDArray[np.float32], int]:
    """Suppress weak noise and downsample grids for bounded FFT work."""
    threshold_raw = ceil((MINIMUM_PRECIPITATION_DBZ - SMHI_OFFSET) / SMHI_GAIN)
    step = max(1, ceil(max(older.shape) / MAX_ANALYSIS_DIMENSION))
    old = older[::step, ::step].astype(np.float32, copy=False)
    new = newer[::step, ::step].astype(np.float32, copy=False)
    old = np.where(old >= threshold_raw, np.log1p(old), 0.0)
    new = np.where(new >= threshold_raw, np.log1p(new), 0.0)
    return old, new, step


def _phase_correlation_shift(
    older: NDArray[np.float32], newer: NDArray[np.float32]
) -> tuple[int, int, float]:
    """Return row/column displacement that moves older data toward newer data."""
    old_fft = np.fft.fft2(older)
    new_fft = np.fft.fft2(newer)
    cross_power = new_fft * old_fft.conj()
    cross_power /= np.maximum(np.abs(cross_power), np.finfo(np.float64).eps)
    correlation = np.fft.ifft2(cross_power)
    magnitude = np.abs(correlation)
    peak_row, peak_column = np.unravel_index(np.argmax(magnitude), magnitude.shape)
    rows, columns = magnitude.shape
    if peak_row > rows // 2:
        peak_row -= rows
    if peak_column > columns // 2:
        peak_column -= columns
    peak_ratio = float(magnitude.max() / (np.mean(magnitude) + 1e-9))
    return int(peak_row), int(peak_column), peak_ratio


def _wet_overlap(
    older: NDArray[np.float32], newer: NDArray[np.float32], dy: int, dx: int
) -> float:
    """Score wet-pixel agreement after a non-wrapping integer translation."""
    row_start_old = max(0, -dy)
    row_end_old = min(older.shape[0], older.shape[0] - dy)
    col_start_old = max(0, -dx)
    col_end_old = min(older.shape[1], older.shape[1] - dx)
    row_start_new = max(0, dy)
    row_end_new = row_start_new + (row_end_old - row_start_old)
    col_start_new = max(0, dx)
    col_end_new = col_start_new + (col_end_old - col_start_old)
    if row_end_old <= row_start_old or col_end_old <= col_start_old:
        return 0.0
    old_wet = older[row_start_old:row_end_old, col_start_old:col_end_old] > 0
    new_wet = newer[row_start_new:row_end_new, col_start_new:col_end_new] > 0
    union = np.count_nonzero(old_wet | new_wet)
    if union == 0:
        return 0.0
    return float(np.count_nonzero(old_wet & new_wet) / union)


def _speed_kmh(
    dx: float, dy: float, interval_seconds: float, pixel_x_m: float, pixel_y_m: float
) -> float:
    """Return speed in km/h using the frame's projected pixel resolution."""
    distance_m = hypot(dx * pixel_x_m, dy * pixel_y_m)
    return distance_m / interval_seconds * 3.6


def _heading_degrees(dx: float, dy: float) -> float:
    """Convert image displacement to 0° north, 90° east geographic heading."""
    return (degrees(atan2(dx, -dy)) + 360.0) % 360.0
