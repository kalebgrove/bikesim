import pytest

from backend.engine import optimizer


@pytest.fixture
def hilly_course(make_route):
    # 400 m flat, 400 m at 6%, 400 m at -6%, 300 m flat; straight, so no corners
    pts, ele = [], 0.0
    for y in range(0, 1500, 10):
        grade = 0.06 if 400 <= y < 800 else -0.06 if 800 <= y < 1200 else 0.0
        pts.append((0.0, float(y), ele))
        ele += grade * 10
    return optimizer.Course(make_route(pts), (0.0, 0.0), 1.225)


def test_dp_beats_constant_cp_within_w_prime(rider, hilly_course):
    V = optimizer.solve(rider, hilly_course)
    plan = optimizer.ride(rider, hilly_course, V)
    constant = optimizer.ride(rider, hilly_course, constant_power=rider.ftp)
    assert plan.total_time < constant.total_time
    assert min(plan.w_prime) >= 0.0
    # The value function from rest with full W' predicts the ride (interpolation error only)
    assert V[0][0, -1] == pytest.approx(plan.total_time, rel=0.01)


def test_dp_spends_w_prime_on_the_climb(rider, hilly_course):
    plan = optimizer.ride(rider, hilly_course, optimizer.solve(rider, hilly_course))
    climb = [p for s, p in zip(plan.starts, plan.powers) if 400 <= s < 800]
    descent = [p for s, p in zip(plan.starts, plan.powers) if 800 <= s < 1200]
    assert sum(climb) / len(climb) > rider.ftp > sum(descent) / len(descent)


def test_segment_w_prime_is_affine(rider, hilly_course):
    # One ride gives W'_end for every W'_start: a w + b. Above CP it drains 1:1 (a = 1).
    seg = optimizer.ride_segment(rider, hilly_course, 400.0, 450.0, 8.0, 500.0, 0.5)
    assert seg.a == pytest.approx(1.0)
    assert seg.b < 0.0
    assert seg.w_needed == pytest.approx(-seg.b)
