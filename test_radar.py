"""Tests for SMHI radar-coordinate and PNG intensity conversion."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.rain_nowcast import radar


class _FakeImage:
    size = (200, 100)

    def __init__(self, pixel: tuple[int, int, int, int]) -> None:
        self._pixel = pixel

    def __enter__(self) -> _FakeImage:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def convert(self, mode: str) -> _FakeImage:
        assert mode == "RGBA"
        return self

    def getpixel(self, index: tuple[int, int]) -> tuple[int, int, int, int]:
        assert index == (100, 50)
        return self._pixel


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


def test_sample_rain_intensity_converts_smhi_png_color(
    monkeypatch: pytest.MonkeyPatch, center_radar_grid: None
) -> None:
    """A PNG palette colour is converted with SMHI's documented Z-R relation."""
    monkeypatch.setattr(
        radar.Image, "open", lambda _: _FakeImage((10, 208, 10, 255))
    )

    assert radar.sample_rain_intensity(b"png", 59.33, 18.07) == 0.63


def test_sample_rain_intensity_handles_transparent_pixel(
    monkeypatch: pytest.MonkeyPatch, center_radar_grid: None
) -> None:
    """Transparent PNG pixels are reported as no rain."""
    monkeypatch.setattr(radar.Image, "open", lambda _: _FakeImage((0, 0, 0, 0)))

    assert radar.sample_rain_intensity(b"png", 59.33, 18.07) == 0.0


def test_sample_rain_intensity_rejects_unknown_color(
    monkeypatch: pytest.MonkeyPatch, center_radar_grid: None
) -> None:
    """An unexpected SMHI palette value surfaces as an update error."""
    monkeypatch.setattr(radar.Image, "open", lambda _: _FakeImage((1, 2, 3, 255)))

    with pytest.raises(ValueError, match="unknown radar colour"):
        radar.sample_rain_intensity(b"png", 59.33, 18.07)
