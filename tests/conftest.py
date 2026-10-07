import math
import os

import pytest

from backend.engine.rider import Rider
from backend.engine.route import Route

EARTH_RADIUS_M = 6371000.0
ORIGIN_LAT, ORIGIN_LON = 43.74, 7.42  # Monaco, so synthetic routes sit at a realistic latitude
STAGE_1_GPX = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "stage-1-route.gpx")


def xy_to_latlon(x_east_m: float, y_north_m: float) -> tuple[float, float]:
    # Local tangent plane (metres east/north of ORIGIN) -> degrees. Accurate to well under
    # 1 mm over a few km, which is plenty for routes built in the tests.
    lat = ORIGIN_LAT + math.degrees(y_north_m / EARTH_RADIUS_M)
    lon = ORIGIN_LON + math.degrees(x_east_m / (EARTH_RADIUS_M * math.cos(math.radians(ORIGIN_LAT))))
    return lat, lon


@pytest.fixture
def make_route():
    # Build a Route from (x_east_m, y_north_m, elevation_m) tuples.
    def _make(xy_ele):
        return Route([(*xy_to_latlon(x, y), ele) for x, y, ele in xy_ele])
    return _make


@pytest.fixture
def straight_route(make_route):
    # Factory: straight line of `length_m` at constant `grade_pct`, heading north by default.
    def _make(length_m=1000.0, grade_pct=0.0, spacing_m=10.0, heading="north"):
        n = int(length_m / spacing_m) + 1
        pts = []
        for i in range(n):
            s = i * spacing_m
            x, y = (0.0, s) if heading == "north" else (s, 0.0)
            pts.append((x, y, s * grade_pct / 100))
        return make_route(pts)
    return _make


@pytest.fixture
def rider():
    # Same rider as rl-agents/train.py: 80 kg system, CdA 0.30, Crr 0.005.
    return Rider(
        rider_mass=70.0,
        bike_mass=10.0,
        ftp=250.0,
        f_max=1000.0,
        cda=0.3,
        crr=0.005,
        inertia=0.15,
        wheel_radius=0.35,
        metabolic_efficiency=0.22,
    )


@pytest.fixture(scope="session")
def stage_1_route():
    return Route.get_route_from_gpx(STAGE_1_GPX)
