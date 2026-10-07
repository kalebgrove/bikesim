# Pins whole-ride results on the real route. These are not "correct" values, just the
# current ones: if a change moves them, decide whether that was intended, then update.

import pytest

from backend.engine import physics


def test_stage_1_route_length(stage_1_route):
    assert stage_1_route.total_distance() == pytest.approx(9796.18, abs=0.01)


def test_stage_1_constant_250w_baseline(rider, stage_1_route):
    # The RL baseline from CLAUDE.md: constant 250 W with auto-braking, no wind = 19.3 min.
    results, kcal = physics.simulate(rider, stage_1_route, (0.0, 0.0), 250.0, 0.5, 1.225)
    ride_time_s = len(results) * 0.5
    assert ride_time_s == pytest.approx(1159.5, abs=1.0)  # 19.33 min
    assert kcal == pytest.approx(305.004, rel=1e-4)
