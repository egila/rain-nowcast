# Developer documentation

## Architecture

`RainNowcastCoordinator` polls SMHI's composite metadata endpoint with
`format=png`, selects the newest PNG from `lastFiles`, and downloads it
using Home Assistant's shared `aiohttp` session. The 5-minute coordinator
interval matches SMHI's normal publication cadence.

PNG decoding is run through `hass.async_add_executor_job`; network I/O, setup,
updates, and entity lifecycle are asynchronous. Home Assistant already ships
Pillow for image handling, avoiding a platform-specific native decoder. A
single pixel is read at the configured home location:

1. `pyproj` converts WGS84 longitude/latitude to SWEREF 99 TM (EPSG:3006).
2. The projected point maps to the published Sweden-composite extent.
3. The PNG pixel colour is mapped to dBZ using SMHI's published palette.
4. Values below 5 dBZ are reported as no rain; all other values use SMHI's
   `Z = 10 log10(200 R^1.5)` relation to calculate `R` in mm/h.

The implementation deliberately does not store frames. Phase 2 should retain
a bounded frame history, identify motion vectors, and only then add ETA,
confidence, duration, and approaching-rain entities.

## Local checks

Create a Python 3.13 virtual environment, install test dependencies, then run:

```sh
pip install -r requirements_test.txt
ruff check .
pytest --cov=custom_components.rain_nowcast --cov-report=term-missing
```

## Home Assistant quality considerations

- Setup is via Config Flow and there is only one location-derived entry.
- Runtime data is held on the config entry and unloaded through platform
  unload helpers.
- A coordinator owns all source I/O and entities do not make independent API
  calls.
- The entity has a stable unique ID, device information, native unit/device
  class, an attribution, and a valid `cloud_polling` IoT class.
- Errors use `UpdateFailed`, which keeps the last good state visible while
  Home Assistant marks updates unavailable.

## SMHI API references

- [Temporal extent and five-minute cadence](https://opendata.smhi.se/radar/temporal_extent)
- [PNG projection, palette, and Z-R formula](https://opendata.smhi.se/radar/data)
