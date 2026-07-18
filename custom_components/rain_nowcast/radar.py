"""GeoTIFF sampling and SMHI radar-value conversion helpers."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

import numpy as np
from PIL import Image
from pyproj import Transformer

from .const import (
    MAX_EASTING,
    MAX_NORTHING,
    MIN_EASTING,
    MIN_NORTHING,
    RADAR_CRS,
)
from .models import RadarFrame

SMHI_GAIN = 0.4
SMHI_OFFSET = -30.0
SMHI_NO_DATA = 255
SMHI_NO_ECHO = 0
MINIMUM_PRECIPITATION_DBZ = 5.0


class RadarLocationOutsideCoverage(ValueError):
    """Raised when a location cannot be sampled from the Sweden composite."""


def location_to_radar_pixel(
    latitude: float, longitude: float, width: int, height: int
) -> tuple[int, int]:
    """Transform WGS84 latitude/longitude into a Sweden-composite pixel position."""
    transformer = Transformer.from_crs("EPSG:4326", RADAR_CRS, always_xy=True)
    easting, northing = transformer.transform(longitude, latitude)

    if not (
        MIN_EASTING <= easting < MAX_EASTING and MIN_NORTHING < northing <= MAX_NORTHING
    ):
        raise RadarLocationOutsideCoverage

    column = int((easting - MIN_EASTING) / (MAX_EASTING - MIN_EASTING) * width)
    row = int((MAX_NORTHING - northing) / (MAX_NORTHING - MIN_NORTHING) * height)
    return column, row


def sample_rain_intensity(
    geotiff: bytes, latitude: float, longitude: float
) -> float | None:
    """Read a GeoTIFF sample and convert SMHI's raw radar value to mm/h.

    Pillow's prebuilt wheels include TIFF/LZW support, avoiding the unavailable
    ``imagecodecs`` package on Home Assistant OS. SMHI documents values of 0 as
    no echo and 255 as outside radar coverage.
    """
    with Image.open(BytesIO(geotiff)) as image:
        width, height = image.size
        column, row = location_to_radar_pixel(latitude, longitude, width, height)
        value = image.getpixel((column, row))

    if not isinstance(value, int):
        raise ValueError("SMHI GeoTIFF is not an 8-bit grayscale image")
    return raw_value_to_intensity(value)


def raw_value_to_intensity(value: float | int) -> float | None:
    """Convert one SMHI raw reflectivity value into millimetres per hour."""
    if value >= SMHI_NO_DATA:
        return None
    if value <= SMHI_NO_ECHO:
        return 0.0

    dbz = value * SMHI_GAIN + SMHI_OFFSET
    if dbz < MINIMUM_PRECIPITATION_DBZ:
        return 0.0

    # SMHI's Z-R relationship: Z = 10 log10(200 * R^1.5).
    intensity = (10 ** (dbz / 10) / 200) ** (2 / 3)
    return round(intensity, 3)


def decode_radar_frame(geotiff: bytes, timestamp: datetime) -> RadarFrame:
    """Decode a complete SMHI GeoTIFF frame for bounded in-memory prediction.

    The published composite has north at the top of the image. Invalid 255
    values become dry pixels before storage, so they cannot affect phase
    correlation or projected home samples.
    """
    with Image.open(BytesIO(geotiff)) as image:
        if image.mode != "L":
            raise ValueError("SMHI GeoTIFF is not an 8-bit grayscale image")
        width, height = image.size
        data = np.array(image, dtype=np.uint8, copy=True)

    if data.shape != (height, width):
        raise ValueError("SMHI GeoTIFF dimensions do not match decoded raster")
    data[data == SMHI_NO_DATA] = SMHI_NO_ECHO
    return RadarFrame(
        timestamp=timestamp,
        data=data,
        pixel_size_x_m=(MAX_EASTING - MIN_EASTING) / width,
        pixel_size_y_m=(MAX_NORTHING - MIN_NORTHING) / height,
    )
