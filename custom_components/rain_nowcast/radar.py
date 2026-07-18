"""GeoTIFF sampling and SMHI radar-value conversion helpers."""

from __future__ import annotations

from io import BytesIO

from PIL import Image
from pyproj import Transformer

from .const import (
    MAX_EASTING,
    MAX_NORTHING,
    MIN_EASTING,
    MIN_NORTHING,
    RADAR_CRS,
)

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
        MIN_EASTING <= easting < MAX_EASTING
        and MIN_NORTHING < northing <= MAX_NORTHING
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
    if value == SMHI_NO_DATA:
        return None
    if value == SMHI_NO_ECHO:
        return 0.0

    dbz = value * SMHI_GAIN + SMHI_OFFSET
    if dbz < MINIMUM_PRECIPITATION_DBZ:
        return 0.0

    # SMHI's Z-R relationship: Z = 10 log10(200 * R^1.5).
    intensity = (10 ** (dbz / 10) / 200) ** (2 / 3)
    return round(intensity, 3)
