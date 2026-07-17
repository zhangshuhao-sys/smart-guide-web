# Fixed Demo Location Design

## Goal

Permanently display the competition venue location in the frontend even when
the ESP32-P4 cannot obtain a GPS fix indoors.

## Coordinates

- Longitude: `117.149823`
- Latitude: `34.211662`
- Source: Tencent Maps
- Coordinate system: GCJ-02

## Behavior

Define one pair of frontend constants and use them for every location consumer,
regardless of `latest.json` values or `gps_valid`:

- Initial AMap center and device marker
- Displayed longitude and latitude
- GPS status and profile location
- Blue GPS trail points
- AMap reverse geocoding
- Weather lookup

The fixed GCJ-02 coordinate is passed directly to AMap. It must not be passed
through the existing WGS84-to-GCJ-02 conversion.

## Scope

Only `index.html` in the frontend is changed. ESP32 firmware, Huawei OBS data,
the local voice server, and server-side walking-route origins remain unchanged.
Consequently, a route produced from a different server-side origin can still
start away from the fixed frontend marker.

## Verification

- Confirm no active location rendering depends on `d.gps_valid`.
- Confirm all fixed map positions use AMap order `[longitude, latitude]`.
- Confirm the fixed coordinate is not passed to `wgs84ToGcj02()`.
- Run a syntax/static check and inspect the frontend diff.
