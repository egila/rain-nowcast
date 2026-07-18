"""Coordinator for polling SMHI radar images and calculating a nowcast."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    API_PARAMS,
    API_URL,
    CONF_APPROACHING_LEAD_MINUTES,
    CONF_MAX_FORECAST_MINUTES,
    CONF_MIN_MOTION_CONFIDENCE,
    CONF_NEIGHBORHOOD_RADIUS,
    CONF_RAIN_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .frame_cache import RadarFrameCache
from .models import (
    NowcastSettings,
    RadarFrame,
    RadarMotion,
    RainNowcastData,
    RainPrediction,
    is_raining,
)
from .motion import estimate_motion
from .predictor import predict_rain_arrival
from .radar import (
    RadarLocationOutsideCoverage,
    decode_radar_frame,
    location_to_radar_pixel,
    sample_rain_intensity,
)

_LOGGER = logging.getLogger(__name__)
MAX_PREDICTION_FRAME_AGE_MINUTES = 15.0
STARTUP_BACKFILL_FRAMES = 2
_DEFAULT_SETTINGS = NowcastSettings()


class RainNowcastCoordinator(DataUpdateCoordinator[RainNowcastData]):
    """Fetch, decode, and predict from the newest SMHI radar image."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        latitude: float,
        longitude: float,
    ) -> None:
        """Initialize the coordinator for a fixed Home Assistant location."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._config_entry = config_entry
        self._latitude = latitude
        self._longitude = longitude
        self._session = async_get_clientsession(hass)
        self._frames = RadarFrameCache()
        self._rain_started_at: datetime | None = None

    @property
    def frame_cache(self) -> RadarFrameCache:
        """Expose the compact cache metadata to integration diagnostics."""
        return self._frames

    @property
    def settings(self) -> NowcastSettings:
        """Return validated option values, retaining defaults for existing entries."""
        options = self._config_entry.options
        return NowcastSettings(
            rain_threshold=float(
                options.get(CONF_RAIN_THRESHOLD, _DEFAULT_SETTINGS.rain_threshold)
            ),
            approaching_lead_minutes=int(
                options.get(
                    CONF_APPROACHING_LEAD_MINUTES,
                    _DEFAULT_SETTINGS.approaching_lead_minutes,
                )
            ),
            max_forecast_minutes=int(
                options.get(
                    CONF_MAX_FORECAST_MINUTES, _DEFAULT_SETTINGS.max_forecast_minutes
                )
            ),
            min_motion_confidence=float(
                options.get(
                    CONF_MIN_MOTION_CONFIDENCE,
                    _DEFAULT_SETTINGS.min_motion_confidence,
                )
            ),
            neighborhood_radius=int(
                options.get(
                    CONF_NEIGHBORHOOD_RADIUS, _DEFAULT_SETTINGS.neighborhood_radius
                )
            ),
        )

    async def _async_startup_backfill_sources(
        self, metadata: Mapping[str, Any]
    ) -> tuple[tuple[str, str | None], ...]:
        """Find today's recent TIFFs through SMHI's year/month/day archive."""
        latest_source = _latest_geotiff(metadata)
        timestamp = _parse_radar_timestamp(latest_source[1])
        if timestamp is None:
            return (latest_source,)

        try:
            year = _catalog_link(metadata, "years", f"{timestamp.year:04d}")
            year_data = await self._async_get_catalog(year)
            month = _catalog_link(year_data, "months", f"{timestamp.month:02d}")
            month_data = await self._async_get_catalog(month)
            day = _catalog_link(month_data, "days", f"{timestamp.day:02d}")
            day_data = await self._async_get_catalog(day)
            sources = _recent_archive_geotiffs(
                day_data.get("files", []), STARTUP_BACKFILL_FRAMES
            )
        except (ClientError, HomeAssistantError, ValueError) as err:
            _LOGGER.debug("SMHI startup backfill unavailable: %s", err)
            return (latest_source,)

        return _include_latest_source(sources, latest_source)

    async def _async_get_catalog(self, url: str) -> Mapping[str, Any]:
        """Fetch one SMHI archive catalogue level using TIFF-only links."""
        async with self._session.get(url, params=API_PARAMS) as response:
            response.raise_for_status()
            return await response.json()

    def _update_rain_arrival(
        self,
        intensity: float | None,
        motion: RadarMotion | None,
        observed_at: datetime,
    ) -> RainPrediction | None:
        """Keep a fixed arrival timestamp for one continuous rain event."""
        if not is_raining(intensity, self.settings.rain_threshold):
            self._rain_started_at = None
            return None
        if self._rain_started_at is None:
            self._rain_started_at = observed_at
        return RainPrediction(
            eta_minutes=0,
            eta_at=self._rain_started_at,
            predicted_intensity=intensity,
            forecast_horizon_minutes=0,
            motion_confidence=motion.confidence if motion is not None else 0.0,
        )

    async def _async_update_data(self) -> RainNowcastData:
        """Download the newest frame and seed an empty cache from recent history."""
        try:
            async with self._session.get(API_URL, params=API_PARAMS) as response:
                response.raise_for_status()
                metadata: Mapping[str, Any] = await response.json()
        except (ClientError, HomeAssistantError, ValueError) as err:
            message = f"Error communicating with SMHI radar API: {err}"
            raise UpdateFailed(message) from err

        try:
            sources = (
                await self._async_startup_backfill_sources(metadata)
                if not self._frames
                else (_latest_geotiff(metadata),)
            )
        except ValueError as err:
            raise UpdateFailed(
                f"Error communicating with SMHI radar API: {err}"
            ) from err
        latest_source = sources[-1]
        latest_frame: RadarFrame | None = None
        current_intensity: float | None = None

        for image_url, valid_time_text in sources:
            is_latest = (image_url, valid_time_text) == latest_source
            try:
                timestamp = _parse_radar_timestamp(valid_time_text)
                if timestamp is None:
                    raise ValueError("SMHI GeoTIFF response has no valid timestamp")
                async with self._session.get(image_url) as response:
                    response.raise_for_status()
                    geotiff = await response.read()
                if is_latest:
                    frame, current_intensity = await self.hass.async_add_executor_job(
                        _decode_and_sample_frame,
                        geotiff,
                        timestamp,
                        self._latitude,
                        self._longitude,
                    )
                else:
                    frame = await self.hass.async_add_executor_job(
                        decode_radar_frame, geotiff, timestamp
                    )
            except RadarLocationOutsideCoverage as err:
                if is_latest:
                    raise UpdateFailed(
                        "The configured Home Assistant location is outside "
                        "SMHI radar coverage"
                    ) from err
                _LOGGER.debug("Skipping backfill frame outside radar coverage: %s", err)
                continue
            except (ClientError, HomeAssistantError, ValueError) as err:
                if is_latest:
                    message = f"Error communicating with SMHI radar API: {err}"
                    raise UpdateFailed(message) from err
                _LOGGER.debug("Skipping unavailable radar backfill frame: %s", err)
                continue

            self._frames.add(frame)
            if is_latest:
                latest_frame = frame

        if latest_frame is None:
            raise UpdateFailed("SMHI response did not provide a usable latest GeoTIFF")

        frame = latest_frame
        frame_age_minutes = max(
            0.0, (datetime.now(UTC) - frame.timestamp).total_seconds() / 60.0
        )
        motion = None
        prediction = None
        latest_pair = self._frames.latest_pair()
        if latest_pair is not None:
            motion = await self.hass.async_add_executor_job(
                estimate_motion, *latest_pair
            )

        if motion is not None and frame_age_minutes <= MAX_PREDICTION_FRAME_AGE_MINUTES:
            if motion.confidence >= self.settings.min_motion_confidence:
                try:
                    column, row = location_to_radar_pixel(
                        self._latitude,
                        self._longitude,
                        frame.data.shape[1],
                        frame.data.shape[0],
                    )
                    prediction = await self.hass.async_add_executor_job(
                        predict_rain_arrival,
                        frame,
                        motion,
                        row,
                        column,
                        self.settings.rain_threshold,
                        self.settings.max_forecast_minutes,
                        self.settings.neighborhood_radius,
                    )
                except (ArithmeticError, ValueError) as err:
                    _LOGGER.debug("Rain-arrival prediction unavailable: %s", err)
        elif (
            motion is not None and frame_age_minutes > MAX_PREDICTION_FRAME_AGE_MINUTES
        ):
            _LOGGER.debug(
                "Skipping rain-arrival prediction; newest frame is %.1f minutes old",
                frame_age_minutes,
            )

        if frame_age_minutes <= MAX_PREDICTION_FRAME_AGE_MINUTES:
            ongoing_rain = self._update_rain_arrival(
                current_intensity, motion, datetime.now(UTC)
            )
            if ongoing_rain is not None:
                prediction = ongoing_rain

        return RainNowcastData(
            current_intensity=current_intensity,
            radar_timestamp=frame.timestamp,
            radar_timestamp_text=valid_time_text,
            source_url=image_url,
            motion=motion,
            prediction=prediction,
            frame_age_minutes=round(frame_age_minutes, 1),
            cached_frame_count=len(self._frames),
        )


def _decode_and_sample_frame(
    geotiff: bytes, timestamp: datetime, latitude: float, longitude: float
) -> tuple[RadarFrame, float | None]:
    """Decode one complete frame and sample its current home-location intensity."""
    frame = decode_radar_frame(geotiff, timestamp)
    # The cached frame replaces nodata with zero for correlation. Sample the
    # original TIFF separately so today's intensity still distinguishes nodata
    # from genuinely dry radar, preserving the established sensor behavior.
    return frame, sample_rain_intensity(geotiff, latitude, longitude)


def _parse_radar_timestamp(value: str | None) -> datetime | None:
    """Parse the UTC validity time returned by SMHI metadata."""
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


def _latest_geotiff(metadata: Mapping[str, Any]) -> tuple[str, str | None]:
    """Return the GeoTIFF link and observation time from API metadata."""
    return _recent_geotiffs(metadata, 1)[0]


def _recent_geotiffs(
    metadata: Mapping[str, Any], count: int
) -> tuple[tuple[str, str | None], ...]:
    """Return up to ``count`` distinct GeoTIFFs, ordered oldest to newest."""
    sources: list[tuple[str, str | None]] = []
    seen_identifiers: set[str] = set()
    for file_info in reversed(metadata.get("lastFiles", [])):
        valid_time = file_info.get("valid")
        for image_format in file_info.get("formats", []):
            if image_format.get("key") == "tif" and image_format.get("link"):
                image_url = image_format["link"]
                identifier = valid_time or image_url
                if identifier not in seen_identifiers:
                    sources.append((image_url, valid_time))
                    seen_identifiers.add(identifier)
                break
        if len(sources) >= count:
            break
    if not sources:
        raise ValueError("SMHI response does not contain a GeoTIFF image")
    return tuple(reversed(sources))


def _catalog_link(metadata: Mapping[str, Any], key: str, wanted: str) -> str:
    """Return a dated SMHI catalogue link without relying on list ordering."""
    for item in metadata.get(key, []):
        item_key = str(item.get("key", ""))
        if item_key == wanted or item_key.lstrip("0") == wanted.lstrip("0"):
            link = item.get("link")
            if isinstance(link, str) and link:
                return link
    raise ValueError(f"SMHI archive does not contain {key} entry {wanted}")


def _recent_archive_geotiffs(
    files: list[Mapping[str, Any]], count: int
) -> tuple[tuple[str, str], ...]:
    """Return the newest unique dated TIFFs from one SMHI daily archive."""
    sources: dict[datetime, tuple[str, str]] = {}
    for file_info in files:
        valid_time = file_info.get("valid")
        if not isinstance(valid_time, str):
            continue
        timestamp = _parse_radar_timestamp(valid_time)
        if timestamp is None:
            continue
        for image_format in file_info.get("formats", []):
            image_url = image_format.get("link")
            if image_format.get("key") == "tif" and isinstance(image_url, str):
                sources[timestamp] = (image_url, valid_time)
                break
    if not sources:
        raise ValueError("SMHI daily archive does not contain a GeoTIFF image")
    return tuple(source for _, source in sorted(sources.items())[-count:])


def _include_latest_source(
    sources: tuple[tuple[str, str], ...], latest: tuple[str, str | None]
) -> tuple[tuple[str, str | None], ...]:
    """Ensure an archive delay cannot omit the newest live GeoTIFF."""
    latest_timestamp = _parse_radar_timestamp(latest[1])
    if latest_timestamp is None or any(valid == latest[1] for _, valid in sources):
        return sources
    combined = (*sources, latest)
    return tuple(
        source
        for _, source in sorted(
            (
                (_parse_radar_timestamp(valid), (url, valid))
                for url, valid in combined
                if _parse_radar_timestamp(valid) is not None
            ),
            key=lambda item: item[0],
        )[-STARTUP_BACKFILL_FRAMES:]
    )
