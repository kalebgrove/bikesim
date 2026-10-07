import math

import pytest

from backend.engine import wind

NORTH, EAST = 0.0, math.pi / 2  # headings: radians clockwise from north


def test_bearing_is_where_the_wind_blows_from():
    # A northerly (from 0 deg) blows toward the south: air velocity (east, north) = (0, -v).
    assert wind.wind_vector_from_bearing(5.0, 0.0) == pytest.approx((0.0, -5.0))
    # An easterly (from 90 deg) blows toward the west.
    assert wind.wind_vector_from_bearing(5.0, 90.0) == pytest.approx((-5.0, 0.0))


@pytest.mark.parametrize(
    "from_bearing, expected_v_rel",
    [
        (0.0, 15.0),    # riding north into a northerly: headwind adds
        (180.0, 5.0),   # southerly is a tailwind: subtracts
        (90.0, 10.0),   # pure crosswind: no longitudinal component
    ],
)
def test_longitudinal_airspeed_riding_north(from_bearing, expected_v_rel):
    w = wind.wind_vector_from_bearing(5.0, from_bearing)
    assert wind.longitudinal_airspeed(NORTH, 10.0, w) == pytest.approx(expected_v_rel, abs=1e-9)


def test_strong_tailwind_makes_v_rel_negative():
    # Tailwind faster than the rider: air pushes from behind, so drag becomes propulsive.
    w = wind.wind_vector_from_bearing(15.0, 180.0)
    assert wind.longitudinal_airspeed(NORTH, 10.0, w) == pytest.approx(-5.0)


def test_apparent_wind_no_wind_is_head_on():
    speed, yaw = wind.apparent_wind((0.0, 10.0), (0.0, 0.0), NORTH)
    assert speed == pytest.approx(10.0)
    assert yaw == pytest.approx(0.0, abs=1e-9)


def test_apparent_wind_crosswind_from_the_right_is_positive_yaw():
    # Riding north at 10 m/s, 10 m/s wind from the east (rider's right):
    # apparent air = wind - bike = (-10, -10), arriving from 45 deg right of the nose.
    speed, yaw = wind.apparent_wind((0.0, 10.0), wind.wind_vector_from_bearing(10.0, 90.0), NORTH)
    assert speed == pytest.approx(10.0 * math.sqrt(2))
    assert yaw == pytest.approx(45.0)


def test_apparent_wind_is_relative_to_heading():
    # Same situation rotated: riding east with wind from the south (rider's right).
    speed, yaw = wind.apparent_wind((10.0, 0.0), wind.wind_vector_from_bearing(10.0, 180.0), EAST)
    assert speed == pytest.approx(10.0 * math.sqrt(2))
    assert yaw == pytest.approx(45.0)


def test_apparent_wind_from_behind_is_180():
    # 10 m/s tailwind overtaking a rider doing 5 m/s: net air from straight behind.
    _, yaw = wind.apparent_wind((0.0, 5.0), wind.wind_vector_from_bearing(10.0, 180.0), NORTH)
    assert abs(yaw) == pytest.approx(180.0)
