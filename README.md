# Rain Nowcast

`rain_nowcast` is a HACS-compatible custom integration for Home Assistant OS.
It downloads SMHI's official Sweden radar composite as a GeoTIFF every five
minutes and reports the current rain intensity at Home Assistant's configured
home location.

> This is Phase 1. It intentionally implements only `sensor.rain_intensity`.
> ETA, confidence, duration, and approaching-rain entities are planned for the
> frame-history nowcasting phase; exposing them before they are computed would
> be misleading.

## Features

- Fully asynchronous Home Assistant integration with `DataUpdateCoordinator`
- Config Flow setup; no API key and no coordinates to enter
- Converts the home latitude/longitude from WGS84 into SMHI's SWEREF 99 TM
  radar grid
- Reports precipitation intensity in `mm/h`, with radar observation time and
  source URL as attributes
- Handles locations outside the Sweden radar composite gracefully

## Installation with HACS

1. In HACS, add this repository as a **Custom repository** of type
   **Integration**.
2. Download **Rain Nowcast** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration**, then add
   **Rain Nowcast**.

The integration uses the latitude and longitude under **Settings → System →
General**. It supports locations in SMHI's Sweden-composite coverage area.

## Entity roadmap

| Entity | Unit | Phase |
| --- | --- | --- |
| `sensor.rain_intensity` | `mm/h` | Implemented |
| `sensor.rain_eta` | minutes | Planned |
| `sensor.rain_confidence` | percent | Planned |
| `sensor.rain_duration` | minutes | Planned |
| `binary_sensor.rain_approaching` | on/off | Planned |

`0` means no echo. `unknown` means that the configured location is outside
radar coverage or the source was unavailable. Rainfall is calculated from
SMHI's documented reflectivity relationship, so it is a radar estimate rather
than a rain-gauge reading.

## Development

See [developer documentation](docs/development.md). This project is licensed
under the [MIT License](LICENSE).

## Data attribution

Radar data is provided by SMHI Open Data. See SMHI's
[radar API documentation](https://opendata.smhi.se/radar/) and applicable
[terms of use](https://www.smhi.se/data/om-smhis-data/om-smhis-oppna-data).
