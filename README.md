# Rain Nowcast

`rain_nowcast` is a HACS-compatible custom integration for Home Assistant OS.
It downloads SMHI's official Sweden radar composite as a GeoTIFF every five
minutes, reports the current rain intensity at Home Assistant's configured
home location, and estimates near-term rain arrival.

Rain Nowcast is an unofficial integration and is not affiliated with or
endorsed by SMHI.

## Features

- Config Flow setup with no API key or manually entered coordinates
- Converts Home Assistant's WGS84 home location to SMHI's SWEREF 99 TM radar
  grid
- Reports current precipitation intensity in `mm/h`
- Keeps up to 12 radar frames only in memory and estimates one global motion
  vector from the newest two frames
- Projects the newest frame in five-minute steps up to 60 minutes, with
  configurable rain threshold, lead time, confidence, horizon, and sampling
  radius
- Uses asynchronous network I/O and Home Assistant's executor for TIFF/
  NumPy processing

## Installation with HACS

1. In HACS, add this repository as a **Custom repository** of type
   **Integration**.
2. Download **Rain Nowcast** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration**, then add
   **Rain Nowcast**.

The integration uses the latitude and longitude under **Settings → System →
General**. It supports locations in SMHI's Sweden-composite coverage area.

## Entities

| Entity | Meaning |
| --- | --- |
| `sensor.rain_intensity` | Current radar-estimated rain intensity in `mm/h`. |
| `binary_sensor.rain_now` | On when the latest radar sample at home meets the configured rain threshold. |
| `sensor.rain_eta` | Timestamp for the predicted arrival; frozen for the duration of a detected rain event and unavailable when no rain is forecast within the selected horizon. |
| `binary_sensor.rain_approaching` | On for a sufficiently confident rain arrival within the configured lead time. |
| `sensor.rain_confidence` | Phase-correlation confidence in percent. |
| `sensor.radar_motion_x` / `sensor.radar_motion_y` | Eastward and southward movement per radar update, in pixels. |
| `sensor.radar_speed` / `sensor.radar_heading` | Estimated motion speed in `km/h` and heading (0° north, 90° east). |
| `sensor.radar_frame_age` | Age of the newest source frame in minutes. |

On startup the integration follows SMHI's daily archive and downloads the two
newest distinct GeoTIFF frames to seed the motion cache. Motion and ETA can
therefore normally be available immediately. If SMHI has only one usable recent
frame, current intensity remains available and prediction entities stay
unavailable until the next update.

## Predictor behavior and limits

The first-generation predictor treats all precipitation in the Sweden radar
composite as moving with one global translation vector. It uses phase
correlation on thresholded, downsampled radar arrays and samples the projected
field in a small configurable neighborhood around home. It does not use
optical flow, machine learning, cell tracking, or growth/decay modelling.

This makes the 5–30 minute range generally the most useful. Treat 60-minute
results as a coarse indication. Predictions can be poor when precipitation
grows, dissipates, splits, merges, is blocked by terrain, or moves differently
in different parts of the radar image. Stale frames (older than 15 minutes) do
not produce a fresh ETA.

`sensor.rain_duration` is intentionally not exposed: a global translation
model cannot estimate rain duration reliably without modelling precipitation
evolution.

Configure threshold, lead time, maximum horizon, minimum confidence, and home
sampling radius via **Settings → Devices & services → Rain Nowcast →
Configure**. Existing configuration entries do not need to be recreated.

## Automation example

```yaml
alias: Rain approaching
triggers:
  - trigger: state
    entity_id: binary_sensor.rain_approaching
    to: "on"
actions:
  - action: notify.notify
    data:
      title: Rain approaching
      message: >
        Rain is expected in approximately
        {{ state_attr('binary_sensor.rain_approaching', 'eta_minutes') }}
        minutes.
mode: single
```

## Development

See [developer documentation](development.md). This project is licensed under
the [MIT License](LICENSE).

## Data attribution

Radar data is provided by SMHI Open Data. See SMHI's
[radar API documentation](https://opendata.smhi.se/radar/) and applicable
[terms of use](https://www.smhi.se/data/om-smhis-data/om-smhis-oppna-data).
