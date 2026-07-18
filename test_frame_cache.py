"""Tests for the bounded radar-frame cache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np

from custom_components.rain_nowcast.frame_cache import RadarFrameCache
from custom_components.rain_nowcast.models import RadarFrame


def _frame(minutes: int) -> RadarFrame:
    return RadarFrame(
        timestamp=datetime(2026, 7, 18, tzinfo=UTC) + timedelta(minutes=minutes),
        data=np.zeros((4, 4), dtype=np.uint8),
        pixel_size_x_m=1000,
        pixel_size_y_m=1000,
    )


def test_cache_orders_out_of_order_frames_and_rejects_duplicates() -> None:
    """Frames remain chronological and duplicate timestamps are ignored."""
    cache = RadarFrameCache(max_frames=4)

    assert cache.add(_frame(10))
    assert cache.add(_frame(0))
    assert cache.add(_frame(5))
    assert not cache.add(_frame(5))

    assert [frame.timestamp.minute for frame in cache.frames] == [0, 5, 10]
    latest_pair = cache.latest_pair()
    assert latest_pair is not None
    assert [frame.timestamp.minute for frame in latest_pair] == [5, 10]


def test_cache_enforces_its_bounded_size() -> None:
    """The oldest frames are discarded once the configured bound is reached."""
    cache = RadarFrameCache(max_frames=3)
    for minute in (0, 5, 10, 15):
        assert cache.add(_frame(minute))

    assert len(cache) == 3
    assert [frame.timestamp.minute for frame in cache] == [5, 10, 15]
