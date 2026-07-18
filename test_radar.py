"""Tests for SMHI radar-coordinate and GeoTIFF intensity conversion."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from PIL import Image

from custom_components.rain_nowcast import radar


class _FakeImage:
    size = (200, 100)

    def __init__(self, value: int) -> None:
        self._value = value

    def __enter__(self) -> _FakeImage:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def getpixel(self, index: tuple[int, int]) -> int:
        assert index == (100, 50)
        return self._value


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
    """A raw GeoTIFF sample is converted with SMHI's Z-R relationship."""
    monkeypatch.setattr(radar.Image, "open", lambda _: _FakeImage(125))

    assert radar.sample_rain_intensity(b"geotiff", 59.33, 18.07) == 0.63


def test_sample_rain_intensity_reads_lzw_geotiff(
    center_radar_grid: None,
) -> None:
    """Pillow decodes the LZW-compressed GeoTIFF used by SMHI."""
    geotiff = BytesIO()
    Image.new("L", (200, 100), 125).save(geotiff, format="TIFF", compression="tiff_lzw")

    assert radar.sample_rain_intensity(geotiff.getvalue(), 59.33, 18.07) == 0.63


@pytest.mark.parametrize(("value", "expected"), [(0, 0.0), (255, None), (80, 0.0)])
def test_sample_rain_intensity_handles_non_rain_values(
    monkeypatch: pytest.MonkeyPatch,
    center_radar_grid: None,
    value: int,
    expected: float | None,
) -> None:
    """No echo, no data, and low reflectivity do not report false rain."""
    monkeypatch.setattr(radar.Image, "open", lambda _: _FakeImage(value))

    assert radar.sample_rain_intensity(b"geotiff", 59.33, 18.07) == expected


def test_decode_radar_frame_replaces_nodata_with_dry_values() -> None:
    """Full-frame decoding preserves dimensions and keeps invalid values out of FFTs."""
    geotiff = BytesIO()
    image = Image.new("L", (2, 3), 120)
    image.putpixel((1, 2), 255)
    image.save(geotiff, format="TIFF", compression="tiff_lzw")

    frame = radar.decode_radar_frame(
        geotiff.getvalue(), datetime(2026, 7, 18, tzinfo=UTC)
    )

    assert frame.data.shape == (3, 2)
    assert frame.data[2, 1] == 0
    assert frame.pixel_size_x_m > 0
    assert frame.pixel_size_y_m > 0
