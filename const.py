"""Constants for the Rain Nowcast integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "rain_nowcast"
PLATFORMS: Final = ["sensor"]

CONF_SCAN_INTERVAL: Final = "scan_interval"
DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=5)

API_URL: Final = (
    "https://opendata-download-radar.smhi.se/api/version/latest/area/sweden/product/comp"
)
API_PARAMS: Final = {"format": "tif"}

# SMHI's Sweden composite is published in SWEREF 99 TM (EPSG:3006).
RADAR_CRS: Final = "EPSG:3006"
MIN_EASTING: Final = 126_648.0
MAX_EASTING: Final = 1_075_693.0
MIN_NORTHING: Final = 5_983_984.0
MAX_NORTHING: Final = 7_771_252.0

ATTRIBUTION: Final = "Radar data from SMHI Open Data"
