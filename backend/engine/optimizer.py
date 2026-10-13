# Dynamic-programming pacing: the pedal power per route segment that minimises finishing
# time, with the same W' fatigue model as the RL env and the same braking envelope as simulate().
#
#   Stage:     segment k of SEGMENT_M along the route
#   State:     (v, w) = speed at the segment start (m/s), W' balance (J); value on grids, interpolated
#   Decision:  pedal power P (W), held for the whole segment
#   Cost:      segment time T (s)
#   Bellman:   V_k(v, w) = min_P [ T_k(v, P) + V_{k+1}(v', w') ],   V_N = 0
#
# Physics doesn't depend on w, so each (segment, v, P) is ridden once. W' does depend on w,
# but every step of its update is affine in w (drain: w - c; recover: f w + (1 - f) W'0),
# so a whole segment is too: w' = a w + b. Storing (a, b) covers every w at once.
#
# Run from bikesim/:  uv run python -m backend.engine.optimizer

import math
from dataclasses import dataclass

import numpy as np

from . import physics
from . import wind as wind_module
from .rider import Rider
from .route import Route

SEGMENT_M = 50.0
SPEED_GRID = np.arange(0.0, 30.0 + 1e-9, 0.5)                 # m/s
W_PRIME = 20_000.0                                            # J, as in rl-agents/env.py
W_GRID = np.arange(0.0, W_PRIME + 1e-9, 1000.0)              # J
POWER_SPACE = np.arange(0.0, 1000.0 + 1e-9, 50.0)            # W, as in rl-agents/env.py
INFEASIBLE = 1e9  # s; finite stand-in for "can't do this", keeps interpolation free of inf * 0 = nan


class Course:
    """Route quantities on the braking-envelope grid, so riding a segment is table lookups."""

    def __init__(self, route: Route, wind_velocity_vector: tuple[float, float], sea_level_density: float):
        self.ds = physics.ENVELOPE_SPACING_M
        self.total = route.total_distance()
        self.wind = wind_velocity_vector
        n = int(self.total // self.ds) + 2
        points = [min(k * self.ds, self.total) for k in range(n)]
        self.slope = [route.slope_at(s)[0] for s in points]
        self.heading = [route.heading_at(s) for s in points]
        self.rho = [physics.air_density_at(sea_level_density, route.position_at(s)[2]) for s in points]
        self.envelope = physics.braking_envelope(route)


@dataclass
class SegmentRide:
    time: float      # s
    v_end: float     # m/s
    a: float         # W'_end = a * W'_start + b
    b: float
    w_needed: float  # J; lowest W'_start that never dips below 0 within the segment


def ride_segment(rider: Rider, course: Course, s0: float, s1: float, v0: float, power: float, dt: float) -> SegmentRide | None:
    # Ride [s0, s1] at constant pedal power from speed v0, braking along the envelope.
    # Same force balance as physics.step. Returns None if the rider can't get moving.
    cp = rider.ftp
    s, v, t = s0, v0, 0.0
    a, b, w_needed = 1.0, 0.0, 0.0
    while s < s1:
        k = min(int(s // course.ds), len(course.slope) - 1)
        v_rel = wind_module.longitudinal_airspeed(course.heading[k], v, course.wind)
        resistive = sum(physics.resistive_components(rider, course.slope[k], v_rel, course.rho[k]))
        v_limit = physics.envelope_speed_at(course.envelope, s)

        h = dt
        v_new, drive, _ = physics.advance_velocity(rider, v, power, resistive, h, v_limit)
        if v_new <= 0.0:
            return None  # stalled: this power can't hold or gain speed here
        last = s + v_new * h >= s1
        if last:
            # Shorten the final step to end on the boundary, so segments join up exactly
            h = (s1 - s) / v_new
            v_new, drive, _ = physics.advance_velocity(rider, v, power, resistive, h, v_limit)

        # W' balance (Skiba, Euler step as in rl-agents/env.py) on the realised pedal power:
        #   P > CP: w -= (P - CP) h
        #   P < CP: w += (CP - P) (W'0 - w) / W'0 * h   =  f w + (1 - f) W'0,  f = 1 - (CP - P) h / W'0
        p = drive * v_new / physics.DRIVETRAIN_EFFICIENCY
        if p > cp:
            b -= (p - cp) * h
            w_needed = max(w_needed, -b / a)  # a w + b >= 0 at this point in the segment
        else:
            f = 1.0 - (cp - p) * h / W_PRIME
            a, b = a * f, b * f + (1.0 - f) * W_PRIME

        s = s1 if last else s + v_new * h
        v = v_new
        t += h
    return SegmentRide(t, v, a, b, w_needed)


def _interp(table: np.ndarray, v: np.ndarray, w: np.ndarray) -> np.ndarray:
    # Bilinear interpolation of table[speed index, W' index]; clamps outside the grids.
    def locate(x, grid):
        step = grid[1] - grid[0]
        f = np.clip(x / step, 0.0, len(grid) - 1)
        i = np.minimum(f.astype(int), len(grid) - 2)
        return i, f - i
    i, tv = locate(v, SPEED_GRID)
    j, tw = locate(w, W_GRID)
    return ((1 - tv) * (1 - tw) * table[i, j] + tv * (1 - tw) * table[i + 1, j]
            + (1 - tv) * tw * table[i, j + 1] + tv * tw * table[i + 1, j + 1])


def _boundaries(course: Course) -> list[float]:
    n = max(1, math.ceil(course.total / SEGMENT_M))
    return [min(k * SEGMENT_M, course.total) for k in range(n + 1)]


def _stage_tables(rider, course, s0, s1, dt):
    # Every (start speed, power) ridden once: arrays of shape (speeds, powers)
    shape = (len(SPEED_GRID), len(POWER_SPACE))
    time = np.full(shape, INFEASIBLE)
    v_end, a, b, w_needed = np.zeros(shape), np.ones(shape), np.zeros(shape), np.zeros(shape)
    for i, v0 in enumerate(SPEED_GRID):
        for j, p in enumerate(POWER_SPACE):
            ride = ride_segment(rider, course, s0, s1, v0, p, dt)
            if ride is not None:
                time[i, j], v_end[i, j], a[i, j], b[i, j], w_needed[i, j] = ride.time, ride.v_end, ride.a, ride.b, ride.w_needed
    return time, v_end, a, b, w_needed


def solve(rider: Rider, course: Course, dt: float = 0.5) -> list[np.ndarray]:
    """Backward pass. Returns V[k] = minimum time (s) from boundary k to the finish, on (SPEED_GRID, W_GRID)."""
    bounds = _boundaries(course)
    n = len(bounds) - 1
    V = [None] * (n + 1)
    V[n] = np.zeros((len(SPEED_GRID), len(W_GRID)))
    w = W_GRID[None, None, :]
    for k in reversed(range(n)):
        time, v_end, a, b, w_needed = _stage_tables(rider, course, bounds[k], bounds[k + 1], dt)
        w_end = a[:, :, None] * w + b[:, :, None]                     # (speeds, powers, W')
        cost = time[:, :, None] + _interp(V[k + 1], np.broadcast_to(v_end[:, :, None], w_end.shape), w_end)
        cost = np.where(w >= w_needed[:, :, None], cost, INFEASIBLE)  # W' may never go negative
        V[k] = np.minimum(cost.min(axis=1), INFEASIBLE)
    return V


@dataclass
class Plan:
    total_time: float              # s
    starts: list[float]            # m, segment start positions
    powers: list[float]            # W, pedal power per segment
    speeds: list[float]            # m/s at each segment end
    w_prime: list[float]           # J at each segment end


def ride(rider: Rider, course: Course, V: list[np.ndarray] | None = None, constant_power: float | None = None, dt: float = 0.5) -> Plan:
    """Forward pass from rest with full W', riding the real (off-grid) state.
    With V: each segment, pick the power minimising time now + V at the next boundary.
    With constant_power instead: ride that (for comparison with the baseline)."""
    bounds = _boundaries(course)
    v, w, total = 0.0, W_PRIME, 0.0
    plan = Plan(0.0, [], [], [], [])
    for k in range(len(bounds) - 1):
        candidates = [constant_power] if constant_power is not None else POWER_SPACE
        best = None
        for p in candidates:
            seg = ride_segment(rider, course, bounds[k], bounds[k + 1], v, p, dt)
            if seg is None or w < seg.w_needed:
                continue
            w_end = seg.a * w + seg.b
            cost = seg.time + (float(_interp(V[k + 1], np.array(seg.v_end), np.array(w_end))) if V is not None else 0.0)
            if best is None or cost < best[0]:
                best = (cost, p, seg, w_end)
        if best is None:
            raise RuntimeError(f"No feasible power for the segment at {bounds[k]:.0f} m")
        _, p, seg, w = best
        v = seg.v_end
        total += seg.time
        plan.starts.append(bounds[k])
        plan.powers.append(float(p))
        plan.speeds.append(v)
        plan.w_prime.append(w)
    plan.total_time = total
    return plan


if __name__ == "__main__":
    import os
    import time as _time

    gpx = os.path.join(os.path.dirname(__file__), "..", "data", "stage-1-route.gpx")
    rider = Rider(rider_mass=70.0, bike_mass=10.0, ftp=250.0, f_max=1000.0, cda=0.3, crr=0.005,
                  inertia=0.15, wheel_radius=0.35, metabolic_efficiency=0.22)  # same rider as rl-agents/train.py
    course = Course(Route.get_route_from_gpx(gpx), (0.0, 0.0), 1.225)

    start = _time.time()
    V = solve(rider, course)
    optimal = ride(rider, course, V)
    baseline = ride(rider, course, constant_power=250.0)
    print(f"Solved {len(optimal.starts)} segments in {_time.time() - start:.0f} s")
    print(f"Constant 250 W: {baseline.total_time / 60:.2f} min")
    print(f"DP optimum:     {optimal.total_time / 60:.2f} min ({optimal.total_time - baseline.total_time:+.1f} s)")
    print(f"  value-function estimate from rest: {V[0][0, -1] / 60:.2f} min")
    print(f"\n{'km':>6} {'P (W)':>6} {'v (km/h)':>9} {'W bal (kJ)':>10}")
    for s, p, v, w in zip(optimal.starts, optimal.powers, optimal.speeds, optimal.w_prime):
        print(f"{s / 1000:6.2f} {p:6.0f} {v * 3.6:9.1f} {w / 1000:10.1f}")
