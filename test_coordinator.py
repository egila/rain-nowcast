"""Tests for coordinator metadata handling."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.rain_nowcast import coordinator
from custom_components.rain_nowcast.coordinator import _latest_geotiff


def test_coordinator_uses_its_config_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first coordinator refresh belongs to the configured entry."""
    coordinator_init = MagicMock()
    monkeypatch.setattr(
        coordinator.DataUpdateCoordinator, "__init__", coordinator_init
    )
    monkeypatch.setattr(coordinator, "async_get_clientsession", MagicMock())
    entry = MagicMock()

    coordinator.RainNowcastCoordinator(MagicMock(), entry, 59.33, 18.07)

    assert coordinator_init.call_args.kwargs["config_entry"] is entry


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
