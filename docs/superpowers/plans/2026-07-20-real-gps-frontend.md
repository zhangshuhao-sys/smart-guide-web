# Real GPS Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixed competition coordinate with validated ATGM336H GPS data from Huawei OBS, without showing a default or stale point as the current location.

**Architecture:** Keep the existing single-file frontend and add small GPS helpers inside `index.html`. Treat OBS coordinates as WGS84, convert only AMap consumers to GCJ-02, create the blue current marker lazily, and clear current-location UI when GPS is invalid while retaining the historical trail.

**Tech Stack:** Static HTML, browser JavaScript, AMap JS SDK, Huawei OBS JSON, Python `unittest`, Python Playwright async API

---

### Task 1: Add real-GPS regression coverage

**Files:**
- Create: `tests/test_real_gps_frontend.py`
- Create: `tests/verify_real_gps_browser.py`
- Test: `index.html`

- [ ] **Step 1: Create the static source-contract test**

Create `tests/test_real_gps_frontend.py`:

```python
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "index.html").read_text(encoding="utf-8")


def function_source(name, next_name):
    pattern = rf"function {name}\([^)]*\) \{{.*?(?=\nfunction {next_name}\()"
    match = re.search(pattern, SOURCE, re.DOTALL)
    if not match:
        raise AssertionError(f"could not find function {name}")
    return match.group(0)


class RealGpsFrontendTests(unittest.TestCase):
    def test_fixed_gps_sources_are_removed(self):
        self.assertNotIn("FIXED_GPS_LAT", SOURCE)
        self.assertNotIn("FIXED_GPS_LNG", SOURCE)
        self.assertNotIn("117.149823", SOURCE)
        self.assertNotIn("34.211662", SOURCE)
        self.assertNotIn("center: [104.07, 30.57]", SOURCE)
        self.assertNotIn("position: [104.07, 30.57]", SOURCE)

    def test_map_does_not_create_a_default_gps_marker(self):
        init_map = function_source("initMap", "createNavigationLine")
        self.assertNotIn("new AMap.Marker", init_map)
        self.assertNotIn("center:", init_map)

    def test_obs_gps_drives_each_coordinate_consumer(self):
        self.assertIn("function getValidGps(d)", SOURCE)
        self.assertIn("d.gps_valid !== true", SOURCE)
        self.assertIn("Number.isFinite(lat)", SOURCE)
        self.assertIn("Number.isFinite(lng)", SOURCE)

        update_gps = function_source("updateCurrentGps", "getUsers")
        self.assertIn("wgs84ToGcj02(gps.lat, gps.lng)", update_gps)
        self.assertIn("fetchAmapLocation(gcj[0], gcj[1])", update_gps)
        self.assertIn("fetchQWeather(gps.lat, gps.lng)", update_gps)
        self.assertIn("trackPoints.push(amapPos)", update_gps)

    def test_invalid_gps_hides_marker_without_clearing_trail(self):
        clear_gps = function_source("clearCurrentGps", "updateCurrentGps")
        self.assertIn("setText('loc-status', '未定位')", clear_gps)
        self.assertIn("setText('profGps', '未定位')", clear_gps)
        self.assertIn("fullMap.remove(fullMarker)", clear_gps)
        self.assertNotIn("trackPoints = []", clear_gps)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Create the browser verification script before implementation**

Create `tests/verify_real_gps_browser.py`:

```python
import asyncio
import json
import urllib.request

from playwright.async_api import async_playwright, expect


OBS_URL = "https://smart-guide-data.obs.cn-north-4.myhuaweicloud.com/latest.json"
PAGE_URL = "http://127.0.0.1:8765/"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def fetch_obs_payload():
    with urllib.request.urlopen(OBS_URL, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


async def main():
    payload = fetch_obs_payload()
    if not payload.get("gps_valid"):
        raise AssertionError("OBS does not currently contain a valid GPS fix")

    location_requests = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            executable_path=CHROME_PATH,
        )
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.add_init_script(
            "localStorage.setItem('sg_logged_in','1');"
            "localStorage.setItem('sg_user','admin');"
        )

        async def handle_local_server(route):
            await route.fulfill(
                status=200,
                content_type="application/json",
                body='{"ok":true,"active":false}',
            )

        await page.route("http://10.163.142.48:8000/**", handle_local_server)
        page.on(
            "request",
            lambda request: location_requests.append(request.url)
            if "restapi.amap.com/v3/geocode/regeo" in request.url
            or "/v7/weather/now" in request.url
            else None,
        )

        await page.goto(PAGE_URL, wait_until="networkidle", timeout=30000)
        await expect(page.locator("#loc-status")).to_have_text("已定位", timeout=15000)
        await expect(page.locator("#loc-lat")).to_have_text(f"{float(payload['latitude']):.6f}")
        await expect(page.locator("#loc-lng")).to_have_text(f"{float(payload['longitude']):.6f}")
        await expect(page.locator("#profGps")).to_have_text(
            f"{float(payload['latitude']):.4f}, {float(payload['longitude']):.4f}"
        )

        valid_state = await page.evaluate(
            """() => ({
                fixedGpsDefined: typeof window.FIXED_GPS_LAT !== 'undefined',
                markerExists: !!window.fullMarker,
                trackLength: window.trackPoints.length
            })"""
        )
        assert valid_state["fixedGpsDefined"] is False
        assert valid_state["markerExists"] is True
        assert valid_state["trackLength"] >= 1

        requests_before_invalid = len(location_requests)
        track_before_invalid = valid_state["trackLength"]
        await page.evaluate(
            """() => updateUI({
                update_time: 'invalid-gps-test',
                gps_valid: false,
                latitude: null,
                longitude: null
            })"""
        )
        await expect(page.locator("#loc-status")).to_have_text("未定位")
        await expect(page.locator("#loc-lat")).to_have_text("--")
        await expect(page.locator("#loc-lng")).to_have_text("--")
        await expect(page.locator("#profGps")).to_have_text("未定位")
        await page.wait_for_timeout(500)

        invalid_state = await page.evaluate(
            """() => ({
                markerExists: !!window.fullMarker,
                trackLength: window.trackPoints.length
            })"""
        )
        assert invalid_state["markerExists"] is False
        assert invalid_state["trackLength"] == track_before_invalid
        assert len(location_requests) == requests_before_invalid
        await browser.close()

    print(
        "PASS real GPS",
        f"lat={float(payload['latitude']):.6f}",
        f"lon={float(payload['longitude']):.6f}",
    )


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Run the static test and verify RED**

Run:

```powershell
python tests/test_real_gps_frontend.py -v
```

Expected: FAIL because `index.html` still contains `FIXED_GPS_LAT`,
`FIXED_GPS_LNG`, and the fixed competition coordinates, and does not yet define
`getValidGps()` or `updateCurrentGps()`.

---

### Task 2: Restore validated real GPS behavior

**Files:**
- Modify: `index.html:890-915`
- Modify: `index.html:931-959`
- Modify: `index.html:1095-1171`
- Modify: `index.html:1452-1478`
- Modify: `index.html:1570-1584`
- Modify: `index.html:1699-1710`
- Test: `tests/test_real_gps_frontend.py`
- Test: `tests/verify_real_gps_browser.py`

- [ ] **Step 1: Remove fixed coordinate state and default marker creation**

Delete these configuration constants:

```javascript
var FIXED_GPS_LNG = 117.149823;
var FIXED_GPS_LAT = 34.211662;
```

Initialize the marker as absent:

```javascript
var fullMap, fullMarker = null, trackLine, trackPoints = [];
```

Replace `initMap()` with a map that has no default GPS coordinate or marker:

```javascript
function initMap() {
  fullMap = new AMap.Map('fullMap', {
    zoom: 15,
    zooms: [3, 20]
  });
  trackLine = new AMap.Polyline({
    map: fullMap,
    path: [],
    strokeColor: '#1677ff',
    strokeWeight: 3,
    strokeOpacity: 0.6
  });
  navigationLine = new AMap.Polyline({
    map: fullMap,
    path: [],
    strokeColor: '#ff4d4f',
    strokeWeight: 6,
    strokeOpacity: 0.85,
    strokeStyle: 'solid',
    lineJoin: 'round'
  });
}
```

- [ ] **Step 2: Add GPS validation and rendering helpers**

Add these functions after `fetchQWeather()` and before the Chart.js section:

```javascript
function getValidGps(d) {
  if (!d || d.gps_valid !== true) return null;
  var lat = Number(d.latitude);
  var lng = Number(d.longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null;
  return { lat: lat, lng: lng };
}

function clearCurrentGps() {
  setText('loc-lat', '--');
  setText('loc-lng', '--');
  setText('loc-status', '未定位');
  setColor('loc-status', 'var(--text3)');
  setText('loc-time', '--');
  setText('loc-addr', '--');
  setText('weather-desc', '--');
  setText('weather-temp', '--');
  setText('weather-wind', '--');
  setText('weather-humi', '--');
  setText('weather-time', '--');
  setText('profGps', '未定位');
  if (fullMap && fullMarker) {
    fullMap.remove(fullMarker);
    fullMarker = null;
  }
  lastGeoLat = null;
  lastGeoLng = null;
  cachedAddr = '--';
  lastWeatherFetch = 0;
}

function updateCurrentGps(d) {
  var gps = getValidGps(d);
  if (!gps) {
    clearCurrentGps();
    return;
  }

  setText('loc-lat', gps.lat.toFixed(6));
  setText('loc-lng', gps.lng.toFixed(6));
  setText('loc-status', '已定位');
  setColor('loc-status', 'var(--success)');
  setText('loc-time', d.update_time || '--');

  var gcj = wgs84ToGcj02(gps.lat, gps.lng);
  var amapPos = [gcj[1], gcj[0]];
  if (!fullMarker && fullMap) {
    fullMarker = new AMap.Marker({
      map: fullMap,
      position: amapPos,
      offset: new AMap.Pixel(-8, -8),
      content: '<div style="width:16px;height:16px;background:#1677ff;border:3px solid #fff;border-radius:50%;box-shadow:0 2px 8px rgba(22,119,255,0.4)"></div>'
    });
  } else if (fullMarker) {
    fullMarker.setPosition(amapPos);
  }

  trackPoints.push(amapPos);
  if (trackLine) trackLine.setPath(trackPoints.slice());
  if (fullMap && trackPoints.length <= 1) fullMap.setCenter(amapPos);
  fetchAmapLocation(gcj[0], gcj[1]);
  fetchQWeather(gps.lat, gps.lng);
}
```

- [ ] **Step 3: Route online, offline, and profile rendering through the helpers**

In the offline branch of `setDeviceOnline(online)`, call `clearCurrentGps()`
before resetting safety and wristband state:

```javascript
    clearCurrentGps();
```

Replace the fixed GPS block in `updateUI(d)` with:

```javascript
  // GPS
  updateCurrentGps(d);
```

Replace the profile GPS line in `updateProfileStatus(d)` with:

```javascript
  // GPS
  var gps = getValidGps(d);
  setText('profGps', gps ? gps.lat.toFixed(4) + ', ' + gps.lng.toFixed(4) : '未定位');
```

- [ ] **Step 4: Run the static test and verify GREEN**

Run:

```powershell
python tests/test_real_gps_frontend.py -v
```

Expected: `Ran 4 tests` and `OK`.

- [ ] **Step 5: Run controlled browser verification**

Run from `D:\tmp\smart-guide-web`:

```powershell
python 'C:\Users\zsh\.agents\skills\webapp-testing\scripts\with_server.py' --server "python -m http.server 8765 --bind 127.0.0.1" --port 8765 -- python tests/verify_real_gps_browser.py
```

Expected: exit code `0` and a line beginning with `PASS real GPS lat=` whose
coordinates match the current OBS `latest.json`. The same run also verifies
that invalid GPS hides the marker, preserves the trail, and makes no new AMap
or QWeather request.

- [ ] **Step 6: Check the complete diff**

Run:

```powershell
git diff --check
git diff -- index.html tests/test_real_gps_frontend.py tests/verify_real_gps_browser.py
```

Expected: `git diff --check` exits `0`; the diff is limited to real-GPS
frontend behavior and its tests.

- [ ] **Step 7: Commit the implementation**

```powershell
git add index.html tests/test_real_gps_frontend.py tests/verify_real_gps_browser.py
git commit -m "Restore real GPS frontend tracking"
```

---

### Task 3: Final regression verification

**Files:**
- Verify: `index.html`
- Verify: `tests/test_real_gps_frontend.py`
- Verify: `tests/verify_real_gps_browser.py`

- [ ] **Step 1: Re-run all frontend GPS checks from the committed tree**

Run:

```powershell
python tests/test_real_gps_frontend.py -v
python 'C:\Users\zsh\.agents\skills\webapp-testing\scripts\with_server.py' --server "python -m http.server 8765 --bind 127.0.0.1" --port 8765 -- python tests/verify_real_gps_browser.py
git diff --check HEAD^ HEAD
git status --short
```

Expected: four static tests pass, browser verification prints `PASS real GPS`,
the committed diff check exits `0`, and `git status --short` has no output.
