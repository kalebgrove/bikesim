import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rl-agents"))
from env import BikeSimEnv  # noqa: E402

ARC_RADIUS_M = 20.0  # v_max = sqrt(0.7 * 9.81 * 20) = 11.7 m/s on the flat


@pytest.fixture
def corner_route(make_route):
    # 300 m north, a 90 deg right-hand arc of radius 20 m, then 300 m east. Flat.
    pts = [(0.0, y, 0.0) for y in range(0, 300, 5)]
    for i in range(16):
        phi = math.pi - (math.pi / 2) * i / 15  # centre (20, 300), from (0, 300) to (20, 320)
        pts.append((ARC_RADIUS_M + ARC_RADIUS_M * math.cos(phi), 300.0 + ARC_RADIUS_M * math.sin(phi), 0.0))
    pts += [(x, 320.0, 0.0) for x in range(25, 325, 5)]
    return make_route(pts)


def test_crash_when_step_sweeps_through_corner(rider, corner_route):
    # dt = 2 s at 15 m/s covers ~30 m: start where the rider's own cell is safe, but the
    # tightest point of the corner lies within the step. Checking only the start cell missed this.
    env = BikeSimEnv(rider, corner_route, dt=2.0)
    v = 15.0
    ds = env.LIMIT_SPACING_M
    k_min = min(range(len(env.speed_limits)), key=env.speed_limits.__getitem__)
    assert env.speed_limits[k_min] < 12.5  # the arc is detected as a tight corner

    s = k_min * ds
    while env._speed_limit_over(s, s) <= v:
        s -= ds
    assert k_min * ds - s < 0.9 * v * env.DT  # the step reaches the tightest point

    env.position, env.velocity = s, v
    env.step(0)  # 0 W, no brake
    assert env.crashes == 1
    assert env.velocity == 0.0
    assert env.position == s  # stopped before the corner, not carried past it


def test_no_crash_on_straight(rider, straight_route):
    env = BikeSimEnv(rider, straight_route(length_m=1000.0), dt=2.0)
    env.position, env.velocity = 100.0, 15.0
    env.step(0)
    assert env.crashes == 0
    assert env.position > 100.0


def test_brake_need_is_one_at_hardest_brake_action(rider, corner_route):
    # brake_need = a_req / (500 N / m_eff); 1.0 means the strongest brake action is just enough
    env = BikeSimEnv(rider, corner_route)
    assert env.max_brake_decel == pytest.approx(500.0 / rider.effective_mass)
    env.position, env.velocity = 0.0, 16.0
    dist, limit, a_req = env._binding_curve_ahead()
    assert env._state()[11] == pytest.approx(min(max(a_req / env.max_brake_decel, -2.0), 2.0))
