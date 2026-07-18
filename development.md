# Developer documentation

## Architecture

`RainNowcastCoordinator` polls SMHI's composite metadata endpoint with
`format=tif`, selects the newest GeoTIFF from `lastFiles`, and downloads it
with Home Assistant's shared `aiohttp` session. The five-minute coordinator
interval matches SMHI's normal publication cadence.

Network I/O is asynchronous. TIFF decoding, full-frame NumPy processing,
motion estimation, and extrapolation run through `hass.async_add_executor_job`
so they do not block Home Assistant's event loop. Pillow decodes SMHI's
single-band 8-bit TIFF without `imagecodecs`; NumPy is already supplied by
Home Assistant Core, so no extra runtime package is declared in the manifest.

The relevant modules are:

- `radar.py` converts WGS84 coordinates to the SWEREF 99 TM grid, decodes a
  GeoTIFF frame, and converts raw reflectivity to `mm/h`.
- `frame_cache.py` keeps no more than 12 distinct timestamped `RadarFrame`
  objects in memory, ordered from oldest to newest.
- `motion.py` applies a weak-echo threshold, bounded downsampling, and NumPy
  phase correlation to estimate the older-to-newer displacement. `dx` is east
  (increasing column); `dy` is south (increasing row). The SMHI composite
  mapping is north-to-south, so heading is `atan2(dx, -dy)`.
- `predictor.py` bilinearly extrapolates the newest frame every five minutes
  without border wrapping, then takes the maximum raw value in the configured
  home neighborhood.
- `coordinator.py` keeps compact `RainNowcastData` only; it never exposes
  radar arrays in state or diagnostics.

The SMHI raw values map to dBZ as `value * 0.4 - 30`. Values below 5 dBZ are
treated as dry. All TIFF nodata values (`255`) become zero before cached-frame
processing. The Z-R conversion is `Z = 10 log10(200 R^1.5)`.

## Availability and options

When the cache is empty, the coordinator follows SMHI's year/month/day archive
to download the two newest distinct GeoTIFFs in chronological order. It keeps
the live latest TIFF if the archive has not caught up yet. Later updates
download only the newest frame. Motion and ETA still require two valid,
shape-compatible frames with a plausible interval and sufficient wet-pixel
correlation. A low-confidence or stale frame retains current intensity but
leaves ETA unavailable. Settings are read from the config-entry Options Flow
on every update, so an entry never needs to be recreated.

Normal data conditions (dry radar, duplicate timestamps, incompatible frames,
or no projected arrival) result in unavailable prediction entities, not a
coordinator failure. Diagnostics deliberately omit latitude, longitude, and
all raster data.

`binary_sensor.rain_now` is independent of motion and ETA: it follows the
latest location sample and configured rain threshold. When a sample first
crosses that threshold, the coordinator records a rain-arrival timestamp and
retains it until radar intensity falls below the threshold. This keeps the ETA
stable throughout one rain event.

## Local checks

Create a Python 3.14 virtual environment, install test dependencies, then run:

```sh
pip install -r requirements_test.txt
ruff format --check custom_components test_*.py conftest.py
ruff check .
pytest --cov=custom_components.rain_nowcast --cov-report=term-missing
```

## Home Assistant quality considerations

- Setup uses Config Flow; runtime data belongs to the config entry and is
  unloaded with the platform helpers.
- A single coordinator owns source I/O. Entities do not make independent
  requests.
- Stable unique IDs, device metadata, entity descriptions, native units,
  diagnostic categories, and a timestamp device class preserve recorder-safe
  states.
- Errors fetching or decoding SMHI source data use `UpdateFailed`; optional
  prediction failures do not remove a valid current intensity.

## SMHI API references

- [Temporal extent and five-minute cadence](https://opendata.smhi.se/radar/temporal_extent)
- [GeoTIFF projection, values, gain/offset, and Z-R formula](https://opendata.smhi.se/radar/data)
