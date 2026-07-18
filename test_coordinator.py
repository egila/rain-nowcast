"""Tests for coordinator metadata handling."""

from __future__ import annotations

import pytest

from custom_components.rain_nowcast.coordinator import _latest_png


def test_latest_png_uses_latest_png() -> None:
    """The coordinator chooses a PNG rather than an HDF5 frame."""
    url, valid = _latest_png(
        {
            "lastFiles": [
                {"valid": "2026-07-18 12:00", "formats": [{"key": "h5", "link": "h5"}]},
                {
                    "valid": "2026-07-18 12:00",
                    "formats": [{"key": "png", "link": "png"}],
                },
            ]
        }
    )

    assert (url, valid) == ("png", "2026-07-18 12:00")


def test_latest_png_requires_png() -> None:
    """An incomplete API response raises a useful error."""
    with pytest.raises(ValueError, match="PNG"):
        _latest_png({"lastFiles": []})
