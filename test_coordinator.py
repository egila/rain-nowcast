"""Tests for coordinator metadata handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.rain_nowcast import coordinator
from custom_components.rain_nowcast.coordinator import (
    _catalog_link,
    _include_latest_source,
    _latest_geotiff,
    _recent_archive_geotiffs,
    _recent_geotiffs,
)


class _CatalogResponse:
    """Minimal asynchronous HTTP response for archive-navigation tests."""

    def __init__(self, data: dict[str, object]) -> None:
        self._data = data

    async def __aenter__(self) -> _CatalogResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        """Model a successful SMHI response."""

    async def json(self) -> dict[str, object]:
        """Return one catalogue payload."""
        return self._data


class _CatalogSession:
    """Minimal shared session that serves a fixed archive hierarchy."""

    def __init__(self, catalogues: dict[str, dict[str, object]]) -> None:
        self.catalogues = catalogues
        self.urls: list[str] = []

    def get(self, url: str, **kwargs: object) -> _CatalogResponse:
        """Return the response associated with one archive link."""
        self.urls.append(url)
        return _CatalogResponse(self.catalogues[url])


def test_coordinator_uses_its_config_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first coordinator refresh belongs to the configured entry."""
    coordinator_init = MagicMock()
    monkeypatch.setattr(coordinator.DataUpdateCoordinator, "__init__", coordinator_init)
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


def test_recent_geotiffs_returns_distinct_last_file_entries_in_time_order() -> None:
    """The live metadata helper keeps distinct TIFF entries in time order."""
    sources = _recent_geotiffs(
        {
            "lastFiles": [
                {"valid": "2026-07-18 12:00", "formats": [{"key": "tif", "link": "a"}]},
                {"valid": "2026-07-18 12:05", "formats": [{"key": "tif", "link": "b"}]},
                {"valid": "2026-07-18 12:10", "formats": [{"key": "tif", "link": "c"}]},
                {
                    "valid": "2026-07-18 12:10",
                    "formats": [{"key": "tif", "link": "c-duplicate"}],
                },
            ]
        },
        2,
    )

    assert sources == (("b", "2026-07-18 12:05"), ("c-duplicate", "2026-07-18 12:10"))


def test_archive_backfill_uses_the_newest_dated_geotiffs() -> None:
    """Daily archive files are ordered by validity time, not API list ordering."""
    sources = _recent_archive_geotiffs(
        [
            {"valid": "2026-07-18 12:10", "formats": [{"key": "tif", "link": "c"}]},
            {"valid": "2026-07-18 12:00", "formats": [{"key": "tif", "link": "a"}]},
            {"valid": "2026-07-18 12:05", "formats": [{"key": "tif", "link": "b"}]},
        ],
        2,
    )

    assert sources == (("b", "2026-07-18 12:05"), ("c", "2026-07-18 12:10"))


def test_archive_backfill_includes_latest_live_frame_when_archive_lags() -> None:
    """The freshest live frame replaces an older archive result when necessary."""
    sources = _include_latest_source(
        (("a", "2026-07-18 12:00"), ("b", "2026-07-18 12:05")),
        ("latest", "2026-07-18 12:10"),
    )

    assert sources == (("b", "2026-07-18 12:05"), ("latest", "2026-07-18 12:10"))


def test_catalog_link_matches_zero_padded_archive_keys() -> None:
    """Archive navigation works whether SMHI returns 7 or 07 for a month/day."""
    assert (
        _catalog_link({"months": [{"key": "7", "link": "month"}]}, "months", "07")
        == "month"
    )


async def test_startup_backfill_navigates_the_daily_archive() -> None:
    """A cold cache follows year, month, and day links to collect TIFF history."""
    instance = object.__new__(coordinator.RainNowcastCoordinator)
    session = _CatalogSession(
        {
            "year": {"months": [{"key": "07", "link": "month"}]},
            "month": {"days": [{"key": "18", "link": "day"}]},
            "day": {
                "files": [
                    {
                        "valid": "2026-07-18 12:00",
                        "formats": [{"key": "tif", "link": "older"}],
                    },
                    {
                        "valid": "2026-07-18 12:05",
                        "formats": [{"key": "tif", "link": "latest"}],
                    },
                ]
            },
        }
    )
    instance._session = session

    sources = await instance._async_startup_backfill_sources(
        {
            "years": [{"key": "2026", "link": "year"}],
            "lastFiles": [
                {
                    "valid": "2026-07-18 12:05",
                    "formats": [{"key": "tif", "link": "latest"}],
                }
            ],
        }
    )

    assert session.urls == ["year", "month", "day"]
    assert sources == (("older", "2026-07-18 12:00"), ("latest", "2026-07-18 12:05"))


def test_rain_arrival_timestamp_stays_fixed_until_radar_turns_dry() -> None:
    """An ongoing rain event retains its first observed arrival timestamp."""
    instance = object.__new__(coordinator.RainNowcastCoordinator)
    instance._config_entry = SimpleNamespace(options={})
    instance._rain_started_at = None
    started_at = datetime(2026, 7, 18, 23, 0, tzinfo=UTC)

    first = instance._update_rain_arrival(1.0, None, started_at)
    ongoing = instance._update_rain_arrival(
        0.5, None, started_at + timedelta(minutes=5)
    )
    ended = instance._update_rain_arrival(0.0, None, started_at + timedelta(minutes=10))
    restarted = instance._update_rain_arrival(
        0.2, None, started_at + timedelta(minutes=15)
    )

    assert first is not None
    assert ongoing is not None
    assert first.eta_at == started_at
    assert ongoing.eta_at == started_at
    assert ended is None
    assert restarted is not None
    assert restarted.eta_at == started_at + timedelta(minutes=15)
