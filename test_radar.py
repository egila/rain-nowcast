"""Tests for SMHI radar-coordinate and intensity conversion."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.rain_nowcast import radar


class _FakeImage:
    shape = (100, 200)

    def __init__(self, value: int) -> None:
        self._value = value

    def __getitem__(self, index: tuple[int, int]) -> int:
        assert index == (50, 100)
        return self._value


class _FakeTiff:
    def __init__(self, value: int) -> None:
        self.pages = [MagicMock(asarray=lambda: _FakeImage(value))]

    def __enter__(self) -> _FakeTiff:
        return self

    def __exit__(self, *args: object) -> None:
        return None


@pytest.fixture
def center_radar_grid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any WGS84 coordinate resolve to the centre of the radar grid."""
    transformer = MagicMock()
    transformer.transform.return_value = (601_170.5, 6_877_618.0)
    monkeypatch.setattr(
        radar.Transformer, "from_crs", lambda *args, **kwargs: transformer
    )


def test_location_to_radar_pixel(center_radar_grid: None) -> None:
    """WGS84 coordinates are transformed into raster-column and row indexes."""
    assert radar.location_to_radar_pixel(59.33, 18.07, 200, 100) == (100, 50)


def test_sample_rain_intensity_converts_smhi_value(
    monkeypatch: pytest.MonkeyPatch, center_radar_grid: None
) -> None:
    """A valid sample is converted with SMHI's documented Z-R relationship."""
    monkeypatch.setattr(radar, "TiffFile", lambda _: _FakeTiff(125))

    assert radar.sample_rain_intensity(b"geotiff", 59.33, 18.07) == 0.63


@pytest.mark.parametrize(
    ("value", "expected"), [(0, 0.0), (255, None), (80, 0.0)]
)
def test_sample_rain_intensity_handles_non_rain_values(
    monkeypatch: pytest.MonkeyPatch,
    center_radar_grid: None,
    value: int,
    expected: float | None,
) -> None:
    """No echo, no data, and low reflectivity do not report false rain."""
    monkeypatch.setattr(radar, "TiffFile", lambda _: _FakeTiff(value))

    assert radar.sample_rain_intensity(b"geotiff", 59.33, 18.07) == expected
