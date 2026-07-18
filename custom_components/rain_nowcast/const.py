"""Constants for the Rain Nowcast integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "rain_nowcast"
PLATFORMS: Final = ["sensor", "binary_sensor"]


CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_RAIN_THRESHOLD: Final = "rain_threshold"
CONF_APPROACHING_LEAD_MINUTES: Final = "approaching_lead_minutes"
CONF_MAX_FORECAST_MINUTES: Final = "max_forecast_minutes"
CONF_MIN_MOTION_CONFIDENCE: Final = "min_motion_confidence"
CONF_NEIGHBORHOOD_RADIUS: Final = "neighborhood_radius"
DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=5)


API_URL: Final = "https://opendata-download-radar.smhi.se/api/version/latest/area/sweden/product/comp"
API_PARAMS: Final = {"format": "tif"}


# SMHI's Sweden composite is published in SWEREF 99 TM (EPSG:3006).
RADAR_CRS: Final = "EPSG:3006"
MIN_EASTING: Final = 126_648.0
MAX_EASTING: Final = 1_075_693.0
MIN_NORTHING: Final = 5_983_984.0
MAX_NORTHING: Final = 7_771_252.0


ATTRIBUTION: Final = "Radar data from SMHI Open Data"
