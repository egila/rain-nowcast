"""Deterministic frame extrapolation and arrival prediction helpers."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
from numpy.typing import NDArray

from .models import RadarFrame, RadarMotion, RainPrediction
from .radar import raw_value_to_intensity


def extrapolate_frame(
    frame: RadarFrame, motion: RadarMotion, horizon: timedelta
) -> NDArray[np.float32]:
    """Project a raw radar frame forward without wrapping at the borders."""
    factor = horizon.total_seconds() / motion.interval_seconds
    dy = motion.dy_pixels * factor
    dx = motion.dx_pixels * factor
    height, width = frame.data.shape
    rows, columns = np.indices((height, width), dtype=np.float32)
    source_rows = rows - dy
    source_columns = columns - dx
    row_low = np.floor(source_rows).astype(np.intp)
    column_low = np.floor(source_columns).astype(np.intp)
    row_fraction = source_rows - row_low
    column_fraction = source_columns - column_low
    projected = np.zeros((height, width), dtype=np.float32)
    for source_rows, source_columns, weights in (
        (row_low, column_low, (1 - row_fraction) * (1 - column_fraction)),
        (row_low + 1, column_low, row_fraction * (1 - column_fraction)),
        (row_low, column_low + 1, (1 - row_fraction) * column_fraction),
        (row_low + 1, column_low + 1, row_fraction * column_fraction),
    ):
        valid = (
            (source_rows >= 0)
            & (source_rows < height)
            & (source_columns >= 0)
            & (source_columns < width)
        )
        projected[valid] += (
            frame.data[source_rows[valid], source_columns[valid]] * weights[valid]
        )
    return projected


def predict_rain_arrival(
    frame: RadarFrame,
    motion: RadarMotion,
    row: int,
    column: int,
    rain_threshold: float,
    max_forecast_minutes: int,
    neighborhood_radius: int,
) -> RainPrediction | None:
    """Return the earliest projected rain arrival, or ``None`` within the horizon."""
    if motion.confidence <= 0.0:
        return None
    current_raw = _neighborhood_max(frame.data, row, column, neighborhood_radius)
    current_intensity = raw_value_to_intensity(current_raw)
    if current_intensity is not None and current_intensity >= rain_threshold:
        return RainPrediction(
            eta_minutes=0,
            eta_at=frame.timestamp,
            predicted_intensity=current_intensity,
            forecast_horizon_minutes=0,
            motion_confidence=motion.confidence,
        )

    for minutes in range(5, max_forecast_minutes + 1, 5):
        raw_value = _projected_neighborhood_max(
            frame,
            motion,
            timedelta(minutes=minutes),
            row,
            column,
            neighborhood_radius,
        )
        intensity = raw_value_to_intensity(raw_value)
        if intensity is not None and intensity >= rain_threshold:
            return RainPrediction(
                eta_minutes=minutes,
                eta_at=frame.timestamp + timedelta(minutes=minutes),
                predicted_intensity=intensity,
                forecast_horizon_minutes=minutes,
                motion_confidence=motion.confidence,
            )
    return None


def _neighborhood_max(
    data: NDArray[np.generic], row: int, column: int, radius: int
) -> float:
    """Return the strongest raw value near a location without leaving the grid."""
    row_start = max(0, row - radius)
    row_end = min(data.shape[0], row + radius + 1)
    column_start = max(0, column - radius)
    column_end = min(data.shape[1], column + radius + 1)
    return float(np.max(data[row_start:row_end, column_start:column_end]))


def _projected_neighborhood_max(
    frame: RadarFrame,
    motion: RadarMotion,
    horizon: timedelta,
    row: int,
    column: int,
    radius: int,
) -> float:
    """Sample a projected home neighborhood without allocating a national frame."""
    factor = horizon.total_seconds() / motion.interval_seconds
    dy = motion.dy_pixels * factor
    dx = motion.dx_pixels * factor
    maximum = 0.0
    for destination_row in range(
        max(0, row - radius), min(frame.data.shape[0], row + radius + 1)
    ):
        for destination_column in range(
            max(0, column - radius), min(frame.data.shape[1], column + radius + 1)
        ):
            source_row = destination_row - dy
            source_column = destination_column - dx
            row_low = int(np.floor(source_row))
            column_low = int(np.floor(source_column))
            row_fraction = source_row - row_low
            column_fraction = source_column - column_low
            value = 0.0
            for sample_row, sample_column, weight in (
                (row_low, column_low, (1 - row_fraction) * (1 - column_fraction)),
                (row_low + 1, column_low, row_fraction * (1 - column_fraction)),
                (row_low, column_low + 1, (1 - row_fraction) * column_fraction),
                (row_low + 1, column_low + 1, row_fraction * column_fraction),
            ):
                if (
                    0 <= sample_row < frame.data.shape[0]
                    and 0 <= sample_column < frame.data.shape[1]
                ):
                    value += float(frame.data[sample_row, sample_column]) * weight
            maximum = max(maximum, value)
    return maximum
