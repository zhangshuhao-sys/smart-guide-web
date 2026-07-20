# Real GPS Frontend Design

## Goal

Display the ESP32-P4's real ATGM336H position from Huawei OBS and never present
a fixed competition coordinate as a live GPS fix.

## Data Source

The frontend continues polling `OBS_BASE + /latest.json` every three seconds.
The location source is valid only when all of these conditions hold:

- `gps_valid` is `true`.
- `latitude` and `longitude` are finite numbers.
- Latitude is between `-90` and `90`.
- Longitude is between `-180` and `180`.

The OBS latitude and longitude are ATGM336H WGS84 coordinates. They remain the
values shown in the location and profile views.

## Valid Location Behavior

When a valid OBS location arrives:

- Display the WGS84 latitude and longitude and set the status to `已定位`.
- Create the blue current-location marker if it does not exist.
- Convert WGS84 to GCJ-02 before positioning the AMap marker and blue trail.
- Use the converted GCJ-02 coordinate for AMap reverse geocoding.
- Use the original WGS84 coordinate for QWeather lookup.
- Center the map on the first valid position.
- Display the same WGS84 coordinate in the profile view.

## Invalid Location Behavior

Before the first valid fix, or whenever the latest OBS payload is invalid:

- Display `--` for latitude, longitude, location time, address, and weather.
- Display `未定位` in the location and profile views.
- Remove the blue current-location marker so no fixed or stale point appears to
  be the current position.
- Keep the existing blue historical trail unchanged.
- Do not call AMap reverse geocoding or QWeather.

The map may use its SDK default viewport before the first valid fix, but it must
not create a GPS marker at a default coordinate.

## Coordinate Flow

```text
ATGM336H WGS84 -> Huawei OBS latest.json
                         |
                         +-> displayed latitude/longitude
                         +-> QWeather lookup
                         +-> WGS84-to-GCJ-02 -> AMap marker/trail/address
```

## Scope

Modify only frontend GPS behavior in `index.html` and add focused regression
coverage. Remove `FIXED_GPS_LNG` and `FIXED_GPS_LAT` from active code. Leave the
ESP32 firmware, OBS publication, local voice server, red walking-route layer,
route clearing, satellite layer switching, and server base configuration
unchanged.

## Verification

- Start with a failing regression check against the current fixed-location code.
- Confirm no active `FIXED_GPS_*` constants or fixed competition coordinates
  remain in `index.html`.
- Confirm valid OBS coordinates drive displayed values and AMap positions.
- Confirm invalid GPS state shows `未定位`, hides the current marker, preserves
  the historical trail, and makes no location-dependent API calls.
- Run HTML/JavaScript static checks and `git diff --check`.
- Load the page with controlled valid and invalid OBS responses and inspect the
  rendered location state when the available browser tooling supports it.
