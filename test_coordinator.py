"""Tests for coordinator metadata handling."""

from __future__ import annotations

import pytest

from custom_components.rain_nowcast.coordinator import _latest_geotiff


def test_latest_geotiff_uses_latest_tif() -> None:
    """The coordinator chooses a GeoTIFF rather than an HDF5 frame."""
    url, valid = _latest_geotiff(
        {
            "lastFiles": [
                {"valid": "2026-07-18 12:00", "formats": [{"key": "h5", "link": "h5"}]},
                {
                    "valid": "2026-07-18 12:00",
                    "formats": [
                        {"key": "png", "link": "png"},
                        {"key": "tif", "link": "tif"},
                    ],
                },
            ]
        }
    )

    assert (url, valid) == ("tif", "2026-07-18 12:00")


def test_latest_geotiff_requires_tif() -> None:
    """An incomplete API response raises a useful error."""
    with pytest.raises(ValueError, match="GeoTIFF"):
        _latest_geotiff({"lastFiles": []})
