import math

import pytest

from backend.engine.route import Route


def test_haversine_one_degree_of_latitude():
    # Arc length = R * angle = 6 371 000 m * (pi / 180) = 111 194.9 m
    d = Route.haversine_distance((0.0, 0.0), (1.0, 0.0))
    assert d == pytest.approx(111_194.9, abs=0.1)


def test_haversine_longitude_shrinks_with_latitude():
    # A degree of longitude spans R * cos(lat) * (pi / 180); this fails if trig runs on degrees.
    lat = 60.0
    d = Route.haversine_distance((lat, 0.0), (lat, 1.0))
    assert d == pytest.approx(111_194.9 * math.cos(math.radians(lat)), rel=1e-3)


def test_total_distance_of_straight_route(straight_route):
    route = straight_route(length_m=1000.0)
    assert route.total_distance() == pytest.approx(1000.0, rel=1e-4)


@pytest.mark.parametrize("grade_pct", [-8.0, 0.0, 5.0, 12.0])
def test_slope_is_grade_in_percent(straight_route, grade_pct):
    # Slope convention: rise / run * 100, positive uphill. Away from the ends, smoothing
    # a straight-line profile leaves it unchanged. 7 m spacing: with a spacing that divides
    # the 20 m smoothing window, points land exactly on its +/-10 m edge and float rounding
    # decides whether they're in, which skews the window point to point. Real GPX never
    # spaces points that evenly.
    route = straight_route(length_m=1001.0, grade_pct=grade_pct, spacing_m=7.0)
    slope, *_ = route.slope_at(500.0)
    assert slope == pytest.approx(grade_pct, abs=0.01)


def test_slope_ignores_whole_metre_elevation_steps(make_route):
    # GPX elevations are often quantized to 1 m. A 2% grade sampled every 7 m with rounding
    # has 1 m jumps between flat runs; point-to-point slope would read 0% or ~14%.
    pts = [(0.0, s, float(round(s * 0.02))) for s in range(0, 1001, 7)]
    route = make_route(pts)
    for s in (300.0, 450.0, 600.0):
        slope, *_ = route.slope_at(s)
        assert slope == pytest.approx(2.0, abs=0.5)


def test_heading_is_clockwise_from_north_in_radians(straight_route):
    north = straight_route(heading="north")
    east = straight_route(heading="east")
    assert north.heading_at(500.0) == pytest.approx(0.0, abs=1e-6)
    assert east.heading_at(500.0) == pytest.approx(math.pi / 2, abs=1e-6)


def test_duplicate_points_do_not_break_interpolation(make_route):
    # Real GPX files repeat points (zero-length segments); position_at must not divide by zero.
    route = make_route([(0.0, 0.0, 0.0), (0.0, 10.0, 0.0), (0.0, 10.0, 0.0), (0.0, 20.0, 0.0)])
    assert route.total_distance() == pytest.approx(20.0, rel=1e-4)
    lat, lon, ele = route.position_at(10.0)
    assert all(math.isfinite(v) for v in (lat, lon, ele))
