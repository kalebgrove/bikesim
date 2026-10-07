import math

import pytest

from backend.engine import physics

G = 9.81
RHO = 1.225
ETA = physics.DRIVETRAIN_EFFICIENCY


# --- Forces -------------------------------------------------------------------------------

def test_effective_mass_adds_wheel_inertia(rider):
    # m_eff = m + I / r^2 = 80 + 0.15 / 0.35^2 = 81.22 kg
    assert rider.effective_mass == pytest.approx(80.0 + 0.15 / 0.35 ** 2)


def test_resistive_components_on_flat(rider):
    gravity, rolling, drag = physics.resistive_components(rider, 0.0, 10.0, RHO)
    assert gravity == 0.0
    assert rolling == pytest.approx(80.0 * G * 0.005)            # Crr m g = 3.92 N
    assert drag == pytest.approx(0.5 * RHO * 0.3 * 10.0 ** 2)    # 1/2 rho CdA v^2 = 18.4 N


def test_gravity_uses_angle_from_percent_grade(rider):
    # 10% grade -> theta = atan(0.10); gravity = m g sin(theta), rolling = Crr m g cos(theta)
    theta = math.atan(0.10)
    gravity, rolling, _ = physics.resistive_components(rider, 10.0, 0.0, RHO)
    assert gravity == pytest.approx(80.0 * G * math.sin(theta))
    assert rolling == pytest.approx(80.0 * G * 0.005 * math.cos(theta))
    downhill, _, _ = physics.resistive_components(rider, -10.0, 0.0, RHO)
    assert downhill == pytest.approx(-gravity)


def test_drag_is_signed_with_relative_airspeed(rider):
    # Tailwind faster than the rider (v_rel < 0) pushes: F = 1/2 rho CdA |v_rel| v_rel < 0
    _, _, drag = physics.resistive_components(rider, 0.0, -5.0, RHO)
    assert drag == pytest.approx(-0.5 * RHO * 0.3 * 25.0)


# --- Drive force --------------------------------------------------------------------------

def test_drive_force_tends_to_p_over_v_as_dt_shrinks(rider):
    # dt -> 0: F = eta P / v = 0.975 * 200 / 10 = 19.5 N
    f = physics.drive_force(rider, 10.0, 200.0, 20.0, 1e-6)
    assert f == pytest.approx(ETA * 200.0 / 10.0, rel=1e-4)


@pytest.mark.parametrize("v", [0.0, 0.5, 5.0, 15.0])
def test_drive_force_delivers_target_power_at_end_of_step(rider, v):
    # Defining equation: F * v_new = eta * P, with v_new = v + (F - R) dt / m_eff.
    # From rest this must stay ~P; the old F = P / v_old gave ~6 kW at dt = 0.5.
    p, resistive, dt = 300.0, 30.0, 0.5
    f = physics.drive_force(rider, v, p, resistive, dt)
    assert f < rider.f_max  # otherwise power is legitimately force-limited
    v_new = v + (f - resistive) * dt / rider.effective_mass
    assert f * v_new == pytest.approx(ETA * p, rel=1e-9)


def test_no_pedalling_above_spin_out(rider):
    assert physics.drive_force(rider, physics.SPIN_OUT_SPEED + 0.1, 500.0, 50.0, 0.5) == 0.0


def test_zero_power_gives_zero_force(rider):
    assert physics.drive_force(rider, 5.0, 0.0, 10.0, 0.5) == 0.0


# --- advance_velocity ---------------------------------------------------------------------

def test_advance_velocity_brakes_down_to_limit(rider):
    v_new, drive, braking = physics.advance_velocity(rider, 15.0, 500.0, 10.0, 0.5, v_limit=10.0)
    assert braking
    assert drive == 0.0
    assert v_new == pytest.approx(10.0)


def test_advance_velocity_never_goes_negative(rider):
    v_new, _, _ = physics.advance_velocity(rider, 0.1, 0.0, 500.0, 0.5)
    assert v_new == 0.0


# --- Cornering ----------------------------------------------------------------------------

@pytest.fixture
def circle_route(make_route):
    # Flat half-circle of radius 50 m, points every ~2 m, starting at the origin heading north.
    radius = 50.0
    n = int(math.pi * radius / 2.0)
    pts = []
    for i in range(n + 1):
        phi = math.pi * i / n
        pts.append((radius - radius * math.cos(phi), radius * math.sin(phi), 0.0))
    return make_route(pts), radius


def test_curvature_radius_of_a_circle(circle_route):
    route, radius = circle_route
    mid = route.total_distance() / 2
    assert physics.curvature_radius_at(route, mid) == pytest.approx(radius, rel=0.01)


def test_curvature_of_straight_road_is_effectively_infinite(straight_route):
    assert physics.curvature_radius_at(straight_route(), 500.0) > 1e4


def test_max_cornering_velocity_on_circle(circle_route):
    # v_max = sqrt(mu g R cos(theta)) = sqrt(0.7 * 9.81 * 50) = 18.5 m/s on the flat
    route, radius = circle_route
    mid = route.total_distance() / 2
    v = physics.max_cornering_velocity(route, mid, 0.0)
    assert v == pytest.approx(math.sqrt(0.7 * G * radius), rel=0.01)


def test_braking_envelope_respects_corners_and_decel(stage_1_route):
    # Each grid speed is <= the cornering limit there, and from it the rider can reach the
    # next point by braking at a_net: v_k^2 <= v_{k+1}^2 + 2 a_net ds.
    route = stage_1_route
    ds = physics.ENVELOPE_SPACING_M
    env = physics.braking_envelope(route)
    total = route.total_distance()
    for k in range(len(env) - 1):
        s = min(k * ds, total)
        slope, *_ = route.slope_at(s)
        assert env[k] <= physics.max_cornering_velocity(route, s, slope) + 1e-9
        a_net = max(0.5, physics.MAX_BRAKE_DECEL + G * math.sin(math.atan(slope / 100)))
        assert env[k] ** 2 <= env[k + 1] ** 2 + 2 * a_net * ds + 1e-6


def test_envelope_speed_matches_grid_points():
    env = [10.0, 8.0, 6.0]
    assert physics.envelope_speed_at(env, 0.0) == pytest.approx(10.0)
    assert physics.envelope_speed_at(env, 5.0) == pytest.approx(8.0)
    # Halfway: v^2 interpolates linearly (constant deceleration), not v
    assert physics.envelope_speed_at(env, 2.5) == pytest.approx(math.sqrt((100 + 64) / 2))


# --- Whole-ride sanity --------------------------------------------------------------------

def steady_speed(rider, power, grade_pct=0.0):
    # Solve eta P = (m g sin(theta) + Crr m g cos(theta) + 1/2 rho CdA v^2) v by bisection.
    theta = math.atan(grade_pct / 100)
    lo, hi = 0.01, 30.0
    for _ in range(100):
        v = (lo + hi) / 2
        need = (80.0 * G * (math.sin(theta) + 0.005 * math.cos(theta)) + 0.5 * RHO * 0.3 * v * v) * v
        lo, hi = (v, hi) if need < ETA * power else (lo, v)
    return v


def test_flat_200w_reaches_analytic_steady_speed(rider, straight_route):
    # CLAUDE.md sanity check: ~200 W on flat, no wind -> 34.2 km/h for this rider.
    route = straight_route(length_m=8000.0)
    results, _ = physics.simulate(rider, route, (0.0, 0.0), 200.0, 0.5, RHO)
    final_v = results[-1][1]
    assert final_v == pytest.approx(steady_speed(rider, 200.0), rel=0.005)
    assert final_v * 3.6 == pytest.approx(34.2, abs=0.3)


def test_steep_climb_is_gravity_dominated(rider, straight_route):
    # 10% at 300 W: speed ~ 3.4 m/s, so gravity (77 N) dwarfs drag (~2 N).
    route = straight_route(length_m=1500.0, grade_pct=10.0)
    results, _ = physics.simulate(rider, route, (0.0, 0.0), 300.0, 0.5, RHO)
    v = results[len(results) // 2][1]
    assert v == pytest.approx(steady_speed(rider, 300.0, 10.0), rel=0.01)
    gravity, _, drag = physics.resistive_components(rider, 10.0, v, RHO)
    assert gravity > 20 * drag
