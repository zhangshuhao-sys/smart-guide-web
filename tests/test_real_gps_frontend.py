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
    def test_current_lan_addresses_are_used(self):
        self.assertIn("'http://10.143.137.48:8000'", SOURCE)
        self.assertIn("localStorage.setItem('sg_local_server_base', DEFAULT_LOCAL_SERVER_BASE)", SOURCE)
        self.assertEqual(SOURCE.count("10.163.142.48"), 1)
        self.assertIn('href="http://10.143.137.226/"', SOURCE)
        self.assertIn("var ip = '10.143.137.226'", SOURCE)
        self.assertGreaterEqual(SOURCE.count("10.143.137.226"), 3)
        self.assertNotIn("10.163.142.226", SOURCE)

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

    def test_polylines_are_not_created_or_cleared_with_empty_paths(self):
        self.assertNotIn("path: []", SOURCE)
        self.assertNotIn("setPath([])", SOURCE)

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
