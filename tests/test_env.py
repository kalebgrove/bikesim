import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rl-agents"))
from env import BikeSimEnv  # noqa: E402
from backend.engine import physics  # noqa: E402

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


def test_braking_in_a_corner_lowers_its_limit(rider, corner_route):
    # Friction circle: at 90% of the cornering limit, coasting is fine but a 500 N brake
    # (factor (1 - (6.25 / 6.87)^2)^(1/4) = 0.64) leaves too little grip -> crash.
    env = BikeSimEnv(rider, corner_route, dt=0.1)
    k_min = min(range(len(env.speed_limits)), key=env.speed_limits.__getitem__)
    s, v = k_min * env.LIMIT_SPACING_M, 0.9 * env.speed_limits[k_min]

    env.position, env.velocity = s, v
    env.step(0)  # 0 W, no brake
    assert env.crashes == 0

    env.position, env.velocity = s, v
    env.step(env.n_actions - 1)  # hardest brake
    assert env.crashes == 1


def test_binding_curve_is_the_nearby_limit_not_a_far_one(rider, straight_route):
    # Regression: just under a limit 2 m ahead, with a looser curve 302 m ahead. Ranking by
    # a_req picked the far one (a_req -0.09 vs -2.4 m/s^2, both "speed to spare"), so the agent
    # never saw the limit it then crashed into. Lowest v_allow = sqrt(v_k^2 + 2 a_max d) must win.
    env = BikeSimEnv(rider, straight_route(length_m=1000.0))
    env.speed_limits = [physics.MAX_CORNERING_VELOCITY] * len(env.speed_limits)
    env.speed_limits[20] = 10.0  # at 100 m
    env.speed_limits[80] = 12.0  # at 400 m
    env.position, env.velocity = 98.0, 9.5

    dist, limit, a_req = env._binding_curve_ahead()
    assert (dist, limit) == (pytest.approx(2.0), 10.0)
    assert a_req == pytest.approx((9.5 ** 2 - 10.0 ** 2) / (2 * 2.0))


def test_binding_curve_prefers_the_one_too_fast_to_brake_for(rider, straight_route):
    # Too fast for a near curve: 15 m/s at 20 m (v_allow = sqrt(225 + 2 * 6.16 * 20) = 21.7 m/s)
    # binds before 7 m/s at 300 m (v_allow = sqrt(49 + 2 * 6.16 * 300) = 61.2 m/s).
    env = BikeSimEnv(rider, straight_route(length_m=1000.0))
    env.speed_limits = [physics.MAX_CORNERING_VELOCITY] * len(env.speed_limits)
    env.speed_limits[24] = 15.0  # at 120 m
    env.speed_limits[80] = 7.0   # at 400 m
    env.position, env.velocity = 100.0, 20.0

    dist, limit, a_req = env._binding_curve_ahead()
    assert (dist, limit) == (pytest.approx(20.0), 15.0)
    assert a_req > 0  # needs braking now
