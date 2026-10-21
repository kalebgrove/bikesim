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


def test_brake_need_is_force_to_end_step_on_envelope(rider, corner_route):
    # brake_need = (m_eff (v - v_env) / dt - F_resist) / 500 N: 1.0 = the hardest brake action
    env = BikeSimEnv(rider, corner_route)
    env.position, env.velocity = 250.0, 16.0
    f_req = rider.effective_mass * (16.0 - env._envelope_over_step()) / env.DT - env._resistive_force()
    assert env._state()[11] == pytest.approx(min(max(f_req / 500.0, -2.0), 2.0))


def test_envelope_respects_every_cell_limit(rider, corner_route):
    # The envelope never asks for more than ENVELOPE_MARGIN of the limit of either cell a point touches
    env = BikeSimEnv(rider, corner_route)
    L = env.speed_limits
    for k in range(1, len(L) - 1):
        assert env.envelope[k] <= env.ENVELOPE_MARGIN * min(L[k - 1], L[k], L[k + 1]) + 1e-9


def test_riding_the_envelope_never_crashes(rider, corner_route):
    # Brake with brake_need x 500 N (next 50 N step up), coast near 0, else pedal 1000 W: with
    # only the observation, this rides the corner route crash-free and never pays overspeed.
    env = BikeSimEnv(rider, corner_route, dt=0.5)
    env.W_PRIME_VALUE = 0.0  # isolate the overspeed term in the reward
    s = env.reset()
    overspeed_paid = 0.0
    while not env.finished:
        need = s[11]
        if need > 0:
            a = env.n_power + min(math.ceil(need * 10) - 1, 9)
        else:
            a = 0 if need > -0.3 else env.n_power - 1
        start = env.position
        s, r, *_ = env.step(a)
        expected = env.PROGRESS_REWARD * (min(env.position, env.total_distance) - start) - env.TIME_PENALTY * env.DT
        overspeed_paid += expected - r
    assert env.crashes == 0
    assert overspeed_paid == pytest.approx(0.0, abs=1.0)


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
    # The limit at 100 m binds the whole cell [95, 100] (crash check: lower of a cell's two ends),
    # and the rider at 98 m is already inside it -> distance 0.
    env = BikeSimEnv(rider, straight_route(length_m=1000.0))
    env.speed_limits = [physics.MAX_CORNERING_VELOCITY] * len(env.speed_limits)
    env.speed_limits[20] = 10.0  # at 100 m
    env.speed_limits[80] = 12.0  # at 400 m
    env.position, env.velocity = 98.0, 9.5

    dist, limit = env._binding_curve_ahead()
    assert (dist, limit) == (0.0, 10.0)


def test_binding_curve_prefers_the_one_too_fast_to_brake_for(rider, straight_route):
    # Too fast for a near curve: 15 m/s from 115 m (cell [115, 120], 15 m ahead) binds before
    # 7 m/s at 400 m. Ranked on d - v dt ("still brakeable after this step?"), reported as d.
    env = BikeSimEnv(rider, straight_route(length_m=1000.0))
    env.speed_limits = [physics.MAX_CORNERING_VELOCITY] * len(env.speed_limits)
    env.speed_limits[24] = 15.0  # at 120 m
    env.speed_limits[80] = 7.0   # at 400 m
    env.position, env.velocity = 100.0, 20.0

    dist, limit = env._binding_curve_ahead()
    assert (dist, limit) == (pytest.approx(15.0), 15.0)



@pytest.mark.parametrize("power_action", [2, 5, 20])  # 100 W (refills), 250 W (= CP), 1000 W (drains)
def test_w_prime_pricing_sums_to_the_same_constant_for_every_ride(rider, straight_route, power_action):
    # Spending W' costs W_PRIME_VALUE per J now, refilling earns it, and W' left at the finish is
    # forfeited, so over a finished ride the W' terms add up to -W_PRIME_VALUE * W'_start whatever
    # the pacing: ride time alone still ranks policies.
    env = BikeSimEnv(rider, straight_route(length_m=500.0), dt=0.5)
    env.reset()
    env.velocity = 8.0
    w_terms = 0.0
    while not env.finished and not env._truncated():
        start = env.position
        _, r, *_ = env.step(power_action)
        w_terms += r - (env.PROGRESS_REWARD * (min(env.position, env.total_distance) - start) - env.TIME_PENALTY * env.DT)
    assert env.crashes == 0
    assert w_terms == pytest.approx(-env.W_PRIME_VALUE * env.W_PRIME)


def test_dp_shaping_telescopes_to_minus_the_start_potential(rider, straight_route):
    # r' = r + gamma Phi(s') - Phi(s) with Phi(finish) = 0: over a finished ride the discounted
    # shaping terms sum to -Phi(s_0) = V(start) - min V(0), whatever the pacing, so the optimal policy is unchanged.
    from backend.engine import optimizer
    route = straight_route(length_m=300.0, grade_pct=3.0)
    plain = BikeSimEnv(rider, route, dt=0.5)
    plain.W_PRIME_VALUE = 0.0  # shaping replaces the flat W' price: compare against the env without it
    V = optimizer.solve(rider, optimizer.Course(route, (0.0, 0.0), plain.AIR_DENSITY, envelope=plain.envelope))
    shaped = BikeSimEnv(rider, route, dt=0.5, value_function=V, gamma=0.99)
    plain.reset(); shaped.reset()
    v_start = optimizer.value_at(V, 0.0, 0.0, shaped.W_PRIME, behind_best=True)
    discounted, t = 0.0, 0
    while not shaped.finished:
        action = 20 if t % 3 else 2  # uneven pacing: 100 W, 1000 W, 1000 W, ...
        _, r_plain, *_ = plain.step(action)
        _, r_shaped, *_ = shaped.step(action)
        discounted += 0.99 ** t * (r_shaped - r_plain)
        t += 1
    assert plain.finished and shaped.crashes == 0
    assert discounted == pytest.approx(v_start, rel=1e-6)
