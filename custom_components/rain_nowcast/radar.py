"""PNG sampling and SMHI radar-value conversion helpers."""

from __future__ import annotations

from io import BytesIO
from typing import Final

from PIL import Image
from pyproj import Transformer

from .const import (
    MAX_EASTING,
    MAX_NORTHING,
    MIN_EASTING,
    MIN_NORTHING,
    RADAR_CRS,
)

SMHI_NO_RAIN_DBZ: Final = 5

# The colours used by SMHI's transparent PNG composite for 5–70 dBZ.
# Source: https://opendata.smhi.se/radar/data
SMHI_PNG_COLORS: Final = {
    (0, 50, 255): 5,
    (0, 70, 255): 6,
    (0, 90, 255): 7,
    (0, 110, 255): 8,
    (0, 130, 255): 9,
    (0, 150, 255): 10,
    (0, 170, 255): 11,
    (0, 128, 0): 12,
    (0, 138, 0): 13,
    (0, 148, 0): 14,
    (0, 158, 0): 15,
    (0, 163, 0): 16,
    (0, 168, 0): 17,
    (0, 173, 0): 18,
    (0, 178, 0): 19,
    (10, 208, 10): 20,
    (10, 218, 10): 21,
    (10, 228, 10): 22,
    (10, 238, 10): 23,
    (10, 248, 10): 24,
    (255, 255, 15): 25,
    (255, 246, 15): 26,
    (255, 238, 15): 27,
    (255, 229, 15): 28,
    (255, 220, 15): 29,
    (255, 200, 0): 30,
    (255, 180, 0): 31,
    (255, 160, 0): 32,
    (255, 140, 0): 33,
    (255, 120, 0): 34,
    (255, 35, 35): 35,
    (255, 15, 15): 36,
    (255, 0, 0): 37,
    (235, 0, 0): 38,
    (215, 0, 0): 39,
    (195, 0, 0): 40,
    (175, 0, 0): 41,
    (155, 0, 0): 42,
    (135, 0, 0): 43,
    (115, 0, 0): 44,
    (175, 0, 175): 45,
    (184, 0, 184): 46,
    (193, 0, 193): 47,
    (202, 0, 202): 48,
    (211, 0, 211): 49,
    (219, 0, 219): 50,
    (228, 0, 228): 51,
    (237, 0, 237): 52,
    (246, 0, 246): 53,
    (255, 0, 255): 54,
    (0, 255, 255): 55,
    (13, 255, 255): 56,
    (26, 255, 255): 57,
    (39, 255, 255): 58,
    (51, 255, 255): 59,
    (64, 255, 255): 60,
    (77, 255, 255): 61,
    (90, 255, 255): 62,
    (102, 255, 255): 63,
    (115, 255, 255): 64,
    (128, 255, 255): 65,
    (141, 255, 255): 66,
    (154, 255, 255): 67,
    (166, 255, 255): 68,
    (179, 255, 255): 69,
    (192, 255, 255): 70,
}


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


def sample_rain_intensity(png: bytes, latitude: float, longitude: float) -> float:
    """Read the SMHI PNG sample at a location and return intensity in mm/h.

    SMHI's transparent PNG has no visible colour below 5 dBZ. Those pixels are
    reported as no rain. Other colours map directly to the published dBZ palette.
    """
    with Image.open(BytesIO(png)) as source:
        image = source.convert("RGBA")

    width, height = image.size
    column, row = location_to_radar_pixel(latitude, longitude, width, height)
    red, green, blue, alpha = image.getpixel((column, row))

    if alpha == 0:
        return 0.0

    try:
        dbz = SMHI_PNG_COLORS[(red, green, blue)]
    except KeyError as err:
        raise ValueError("SMHI PNG contains an unknown radar colour") from err

    if dbz < SMHI_NO_RAIN_DBZ:
        return 0.0

    intensity = (10 ** (dbz / 10) / 200) ** (2 / 3)
    return round(intensity, 3)
