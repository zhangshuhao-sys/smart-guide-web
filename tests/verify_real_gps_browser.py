import asyncio
import json
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright, expect


OBS_URL = "https://smart-guide-data.obs.cn-north-4.myhuaweicloud.com/latest.json"
PAGE_URL = (Path(__file__).resolve().parents[1] / "index.html").as_uri()
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def fetch_obs_payload():
    with urllib.request.urlopen(OBS_URL, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


async def main():
    payload = fetch_obs_payload()
    if not payload.get("gps_valid"):
        raise AssertionError("OBS does not currently contain a valid GPS fix")

    location_requests = []
    obs_responses = []
    failed_requests = []
    console_errors = []
    obs_request_count = 0
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

        async def handle_obs(route):
            nonlocal obs_request_count
            obs_request_count += 1
            response_payload = dict(payload)
            response_payload["update_time"] = f"browser-test-{obs_request_count}"
            await route.fulfill(
                status=200,
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"},
                body=json.dumps(response_payload, ensure_ascii=False),
            )

        await page.route("**/latest.json?*", handle_obs)
        await page.route("http://10.163.142.48:8000/**", handle_local_server)
        page.on(
            "response",
            lambda response: obs_responses.append(f"{response.status} {response.url}")
            if "latest.json" in response.url
            else None,
        )
        page.on(
            "requestfailed",
            lambda request: failed_requests.append(f"{request.url} :: {request.failure}"),
        )
        page.on(
            "console",
            lambda message: console_errors.append(f"{message.type}: {message.text}")
            if message.type in ("error", "warning")
            else None,
        )
        page.on(
            "request",
            lambda request: location_requests.append(request.url)
            if "restapi.amap.com/v3/geocode/regeo" in request.url
            or "/v7/weather/now" in request.url
            else None,
        )

        await page.goto(PAGE_URL, wait_until="networkidle", timeout=30000)
        try:
            await expect(page.locator("#loc-status")).to_have_text("已定位", timeout=15000)
        except AssertionError:
            print("OBS_RESPONSES", obs_responses)
            print("FAILED_REQUESTS", failed_requests)
            print("CONSOLE_ERRORS", console_errors)
            raise
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
