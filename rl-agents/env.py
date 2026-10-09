import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import math
from backend.engine import physics
from backend.engine import wind as wind_module
import backend.engine.rider as rider_module
import backend.engine.route as route_module


class BikeSimEnv:
    # Each action is EITHER a pedal power (W) OR a brake force (N), never both.
    POWER_SPACE = [0, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 950, 1000]
    # Capped below tyre grip: mu * m * g = 0.7 * 80 * 9.81 ~ 550 N
    BRAKE_SPACE = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500]
    AIR_DENSITY = 1.225
    DT = 0.1
    MAX_EPISODE_TIME = 10800.0
    W_PRIME = 20_000.0      # J, anaerobic work capacity above critical power (typical 15-25 kJ)
    TIME_PENALTY = 1.0      # reward per second elapsed (negative)
    PROGRESS_REWARD = 0.1   # reward per metre covered (shaping; sums to a constant at the finish)
    CRASH_PENALTY = 200.0   # on top of the time lost re-accelerating from 0; at 50 the agent accepted ~15 crashes/ride instead of braking
    LIMIT_SPACING_M = physics.ENVELOPE_SPACING_M  # speed-limit grid, shared by observation and crash check
    CURVE_HORIZON_M = 500.0
    CURVE_SPEED_CAP = 30.0  # m/s; grid points with a higher limit don't count as curves

    def __init__(self, rider: rider_module.Rider, route: route_module.Route, wind_velocity_vector: tuple[float, float] = (0.0, 0.0), dt: float | None = None):
        self.rider = rider
        self.route = route
        self.wind_velocity_vector = wind_velocity_vector
        self.DT = dt if dt is not None else self.DT
        self.critical_power = rider.ftp  # CP ~ FTP
        # Deceleration from the strongest brake action alone, on the flat: a = F / m_eff (m/s^2).
        # Drag and climbing add to it; descending takes away.
        self.max_brake_decel = max(self.BRAKE_SPACE) / rider.effective_mass

        self.total_distance = route.total_distance()
        self._precompute_speed_limits()

        self.n_power = len(self.POWER_SPACE)
        self.n_brake = len(self.BRAKE_SPACE)
        self.n_actions = self.n_power + self.n_brake

        self.n_state = 12

        self.reset()

    def _precompute_speed_limits(self):
        # Cornering limit v_max = sqrt(mu g R cos(theta)) at every grid point (m/s). The same
        # grid drives both the observation and the crash check, so every limit the agent can
        # crash against is one it was shown.
        ds = self.LIMIT_SPACING_M
        n = int(self.total_distance // ds) + 2
        self.speed_limits = []
        for k in range(n):
            s = min(k * ds, self.total_distance)
            slope, *_ = self.route.slope_at(s)
            self.speed_limits.append(physics.max_cornering_velocity(self.route, s, slope))

    def _speed_limit_over(self, s0: float, s1: float) -> float:
        # Lowest limit over every grid cell the stretch [s0, s1] touches (limit inside a cell =
        # the lower of its two end points). One step can cover several cells (20 m/s * 0.5 s =
        # 10 m = 2 cells), so checking only the start cell lets the rider skip past corners.
        last = len(self.speed_limits) - 2
        k0 = min(max(int(s0 // self.LIMIT_SPACING_M), 0), last)
        k1 = min(max(int(s1 // self.LIMIT_SPACING_M), k0), last)
        return min(self.speed_limits[k0:k1 + 2])

    def _binding_curve_ahead(self):
        # The curve within the horizon that needs the hardest braking from the current speed:
        # argmax over grid points of a_req = (v^2 - v_k^2) / (2 d_k), d floored at 1 m.
        # Starts at the cell the rider is in, so the current limit is always visible.
        # Returns (distance_m, limit_mps, a_req_mps2), or None if no curve is in range.
        ds = self.LIMIT_SPACING_M
        v2 = self.velocity ** 2
        k0 = min(max(int(self.position // ds), 0), len(self.speed_limits) - 1)
        k1 = min(int((self.position + self.CURVE_HORIZON_M) // ds), len(self.speed_limits) - 1)
        best = None
        for k in range(k0, k1 + 1):
            limit = self.speed_limits[k]
            if limit >= self.CURVE_SPEED_CAP:
                continue
            dist = max(k * ds - self.position, 0.0)
            a_req = (v2 - limit ** 2) / (2.0 * max(dist, 1.0))
            if best is None or a_req > best[2]:
                best = (dist, limit, a_req)
        return best

    def _rider_frame_wind(self) -> tuple[float, float]:
        # Wind in the rider's frame (m/s): (headwind, crosswind from the right).
        # The world-frame vector alone is useless to the agent, which doesn't know its heading.
        heading = self.route.heading_at(min(self.position, self.total_distance))
        forward = (math.sin(heading), math.cos(heading))
        right = (math.cos(heading), -math.sin(heading))
        wx, wy = self.wind_velocity_vector
        headwind = -(wx * forward[0] + wy * forward[1])
        crosswind = -(wx * right[0] + wy * right[1])
        return headwind, crosswind

    def _state(self):
        slope = self._slope_at(self.position)

        upcoming = self._binding_curve_ahead()
        if upcoming is not None:
            dist_to_curve, curve_max_speed, a_req = upcoming
            # Deceleration needed to reach the curve at its limit: a_req = (v^2 - v_c^2) / (2 d), m/s^2.
            # Scaled so 1.0 = the agent's hardest brake action (max_brake_decel); negative = speed to spare.
            brake_need = min(max(a_req / self.max_brake_decel, -2.0), 2.0)
            dist_to_curve = min(dist_to_curve, self.CURVE_HORIZON_M) / self.CURVE_HORIZON_M
            curve_max_speed = curve_max_speed / 30.0
        else:
            dist_to_curve = 1.0
            curve_max_speed = 1.0
            brake_need = 0.0

        slope_ahead_50 = self._slope_at(self.position + 50.0)
        slope_ahead_100 = self._slope_at(self.position + 100.0)
        slope_ahead_200 = self._slope_at(self.position + 200.0)

        headwind, crosswind = self._rider_frame_wind()

        return [
            self.velocity / 30.0,
            slope / 30.0,
            self.position / max(self.total_distance, 1.0),
            headwind / 30.0,
            crosswind / 30.0,
            dist_to_curve,
            curve_max_speed,
            slope_ahead_50 / 30.0,
            slope_ahead_100 / 30.0,
            slope_ahead_200 / 30.0,
            self.w_prime_balance / self.W_PRIME,
            brake_need,
        ]

    def _slope_at(self, position):
        position = min(max(position, 0.0), self.total_distance)
        slope, _, _, _, _ = self.route.slope_at(position)
        return slope

    def reset(self):
        self.position = 0.0
        self.velocity = 0.0
        self.time_elapsed = 0.0
        self.crashes = 0
        self.finished = False
        self.mechanical_joules = 0.0
        self.w_prime_balance = self.W_PRIME
        return self._state()

    def action_index_to_values(self, action: int) -> tuple[float, float]:
        if action < self.n_power:
            return self.POWER_SPACE[action], 0.0
        return 0.0, self.BRAKE_SPACE[action - self.n_power]

    def _update_w_prime(self, power: float):
        # W' balance (Skiba): above CP it drains 1:1; below CP it refills, faster when empty.
        #   P > CP: dW'/dt = -(P - CP)
        #   P < CP: dW'/dt = (CP - P) * (W'0 - W') / W'0
        cp = self.critical_power
        if power > cp:
            self.w_prime_balance -= (power - cp) * self.DT
        else:
            self.w_prime_balance += (cp - power) * (self.W_PRIME - self.w_prime_balance) / self.W_PRIME * self.DT
        self.w_prime_balance = min(max(self.w_prime_balance, 0.0), self.W_PRIME)

    def step(self, action: int):
        """Returns (state, reward, terminated, truncated)."""
        p_target, brake_force = self.action_index_to_values(action)
        # Can't ride above CP for longer than W' allows: cap so this step can't overdraw it
        p_target = min(p_target, self.critical_power + self.w_prime_balance / self.DT)

        slope = self._slope_at(self.position)
        start_position = self.position

        heading = self.route.heading_at(self.position)
        v_rel = wind_module.longitudinal_airspeed(heading, self.velocity, self.wind_velocity_vector)

        # No v_limit: the agent must brake for corners itself or crash
        new_position, new_velocity, p_realized = physics.step(
            rider=self.rider,
            route=self.route,
            position=self.position,
            velocity=self.velocity,
            slope=slope,
            v_rel=v_rel,
            p_target=p_target,
            dt=self.DT,
            air_density=self.AIR_DENSITY,
            break_force=brake_force,
        )

        self.time_elapsed += self.DT
        self.mechanical_joules += p_realized * self.DT
        self._update_w_prime(p_realized)

        # The step covers [start, new_position] at new_velocity (position += v_new * dt), so that
        # speed must respect every limit on the way, not just the one where the step started.
        if new_velocity > self._speed_limit_over(start_position, new_position):
            # Crash before the corner: lose the speed (and the time to regain it) plus a fixed penalty.
            # Not terminal, so ending the episode early is never an escape from time penalties.
            self.crashes += 1
            self.velocity = 0.0
            return self._state(), -self.CRASH_PENALTY - self.TIME_PENALTY * self.DT, False, self._truncated()

        self.position, self.velocity = new_position, new_velocity

        # Minimise finishing time. Progress reward is shaping: it sums to the same
        # constant for every finished ride, so only the time term ranks policies.
        reward = self.PROGRESS_REWARD * (min(self.position, self.total_distance) - start_position) - self.TIME_PENALTY * self.DT

        terminated = self.position >= self.total_distance
        self.finished = terminated
        return self._state(), reward, terminated, (not terminated) and self._truncated()

    def _truncated(self) -> bool:
        return self.time_elapsed >= self.MAX_EPISODE_TIME
