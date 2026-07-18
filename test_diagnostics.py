"""Tests for redacted compact diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import numpy as np

from custom_components.rain_nowcast.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.rain_nowcast.frame_cache import RadarFrameCache
from custom_components.rain_nowcast.models import RadarFrame, RainNowcastData


async def test_diagnostics_exclude_radar_arrays_and_location() -> None:
    """Diagnostics contain cache metadata but no grid contents or home location."""
    cache = RadarFrameCache()
    cache.add(
        RadarFrame(
            timestamp=datetime(2026, 7, 18, tzinfo=UTC),
            data=np.ones((2, 2), dtype=np.uint8),
            pixel_size_x_m=1000,
            pixel_size_y_m=1000,
        )
    )
    data = RainNowcastData(
        current_intensity=0.2,
        radar_timestamp=datetime(2026, 7, 18, tzinfo=UTC),
        radar_timestamp_text="2026-07-18 12:00",
        source_url="https://example.invalid/radar.tif",
        motion=None,
        prediction=None,
        frame_age_minutes=2,
        cached_frame_count=1,
    )
    entry = SimpleNamespace(
        runtime_data=SimpleNamespace(data=data, frame_cache=cache, latitude=59.3)
    )

    diagnostics = await async_get_config_entry_diagnostics(None, entry)

    assert diagnostics["cached_frame_count"] == 1
    assert diagnostics["cached_timestamps"] == ["2026-07-18T00:00:00+00:00"]
    assert "latitude" not in diagnostics
    assert "data" not in diagnostics
