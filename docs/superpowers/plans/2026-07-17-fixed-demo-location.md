# Fixed Demo Location Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permanently display Tencent Maps GCJ-02 coordinate `117.149823, 34.211662` throughout the frontend, regardless of OBS GPS state.

**Architecture:** Define a single longitude/latitude constant pair in the existing configuration block. Feed those constants directly to AMap, reverse geocoding, weather, track, and profile rendering; do not call the WGS84 conversion for this fixed GCJ-02 coordinate.

**Tech Stack:** Single-file HTML, browser JavaScript, AMap JS SDK, Python static assertions

---

### Task 1: Permanently use the fixed GCJ-02 location

**Files:**
- Modify: `index.html:887-895`
- Modify: `index.html:929-940`
- Modify: `index.html:1568-1593`
- Modify: `index.html:1717-1721`

- [ ] **Step 1: Run a static assertion that demonstrates the feature is absent**

Run:

```powershell
python -c "from pathlib import Path; s=Path('index.html').read_text(encoding='utf-8'); assert 'FIXED_GPS_LNG = 117.149823' in s and 'FIXED_GPS_LAT = 34.211662' in s"
```

Expected: FAIL with `AssertionError` because the fixed location constants do not exist.

- [ ] **Step 2: Add one fixed GCJ-02 coordinate source**

Add below the API configuration variables:

```javascript
var FIXED_GPS_LNG = 117.149823;
var FIXED_GPS_LAT = 34.211662;
```

- [ ] **Step 3: Initialize AMap from the fixed location**

In `initMap()`, replace both literal default positions with:

```javascript
center: [FIXED_GPS_LNG, FIXED_GPS_LAT],
```

and:

```javascript
position: [FIXED_GPS_LNG, FIXED_GPS_LAT],
```

- [ ] **Step 4: Replace conditional OBS GPS rendering with the fixed location**

Replace the entire `if (d.gps_valid ... ) { ... } else { ... }` GPS block in `updateUI(d)` with:

```javascript
var fixedLat = FIXED_GPS_LAT;
var fixedLng = FIXED_GPS_LNG;
var amapPos = [fixedLng, fixedLat];
setText('loc-lat', fixedLat.toFixed(6));
setText('loc-lng', fixedLng.toFixed(6));
setText('loc-status', '已定位');
setColor('loc-status', 'var(--success)');
setText('loc-time', d.update_time || '--');
if (fullMarker) fullMarker.setPosition(amapPos);
trackPoints.push(amapPos);
if (trackLine) trackLine.setPath(trackPoints.slice());
if (fullMap && trackPoints.length <= 1) fullMap.setCenter(amapPos);
fetchAmapLocation(fixedLat, fixedLng);
fetchQWeather(fixedLat, fixedLng);
```

This intentionally bypasses `wgs84ToGcj02()` because Tencent Maps already supplied GCJ-02 coordinates.

- [ ] **Step 5: Make profile GPS use the same fixed location**

Replace the profile `gps_valid` branch with:

```javascript
setText('profGps', FIXED_GPS_LAT.toFixed(4) + ', ' + FIXED_GPS_LNG.toFixed(4));
```

- [ ] **Step 6: Run fixed-location static checks**

Run:

```powershell
python -c "from pathlib import Path; s=Path('index.html').read_text(encoding='utf-8'); assert 'FIXED_GPS_LNG = 117.149823' in s; assert 'FIXED_GPS_LAT = 34.211662' in s; assert s.count('d.gps_valid && d.latitude && d.longitude') == 0"
```

Expected: exit code 0 with no output.

- [ ] **Step 7: Check diff integrity**

Run:

```powershell
git diff --check
git diff -- index.html
```

Expected: `git diff --check` exits 0; the diff contains only fixed-location changes.

- [ ] **Step 8: Commit the frontend change**

```powershell
git add index.html
git commit -m "Use fixed competition GPS location"
```
