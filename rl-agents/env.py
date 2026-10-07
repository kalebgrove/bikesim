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
    CRASH_PENALTY = 50.0    # on top of the time lost re-accelerating from 0

    def __init__(self, rider: rider_module.Rider, route: route_module.Route, wind_velocity_vector: tuple[float, float] = (0.0, 0.0), dt: float | None = None):
        self.rider = rider
        self.route = route
        self.wind_velocity_vector = wind_velocity_vector
        self.DT = dt if dt is not None else self.DT
        self.critical_power = rider.ftp  # CP ~ FTP

        self.total_distance = route.total_distance()
        self._precompute_curves()

        self.n_power = len(self.POWER_SPACE)
        self.n_brake = len(self.BRAKE_SPACE)
        self.n_actions = self.n_power + self.n_brake

        self.n_state = 11

        self.reset()

    def _precompute_curves(self):
        curves = []
        radius_threshold = 200.0
        step = 5.0
        position = 0.0
        while position < self.total_distance:
            slope, _, _, _, _ = self.route.slope_at(position)
            radius = physics.curvature_radius_at(self.route, position)
            if radius < radius_threshold:
                max_speed = physics.max_cornering_velocity(self.route, position, slope)
                if curves and position - curves[-1][0] < 100.0:
                    if max_speed < curves[-1][1]:
                        curves[-1] = (position, max_speed)
                else:
                    curves.append((position, max_speed))
            position += step
        self.curves = curves

    def _closest_curve_ahead(self, horizon: float = 500.0):
        for curve_pos, max_speed in self.curves:
            dist = curve_pos - self.position
            if 0 < dist <= horizon:
                return dist, max_speed
        return None

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

        upcoming = self._closest_curve_ahead()
        if upcoming is not None:
            dist_to_curve, curve_max_speed = upcoming
            dist_to_curve = min(dist_to_curve, 500.0) / 500.0
            curve_max_speed = curve_max_speed / 30.0
        else:
            dist_to_curve = 1.0
            curve_max_speed = 1.0

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

        max_velocity = physics.max_cornering_velocity(self.route, self.position, slope)
        if self.velocity > max_velocity:
            # Crash: lose the speed (and the time to regain it) plus a fixed penalty.
            # Not terminal, so ending the episode early is never an escape from time penalties.
            self.crashes += 1
            self.velocity = 0.0
            self.time_elapsed += self.DT
            self._update_w_prime(0.0)
            return self._state(), -self.CRASH_PENALTY - self.TIME_PENALTY * self.DT, False, self._truncated()

        heading = self.route.heading_at(self.position)
        v_rel = wind_module.longitudinal_airspeed(heading, self.velocity, self.wind_velocity_vector)

        # No v_limit: the agent must brake for corners itself or crash
        self.position, self.velocity, _, p_realized = physics.step(
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

        # Minimise finishing time. Progress reward is shaping: it sums to the same
        # constant for every finished ride, so only the time term ranks policies.
        reward = self.PROGRESS_REWARD * (min(self.position, self.total_distance) - start_position) - self.TIME_PENALTY * self.DT

        terminated = self.position >= self.total_distance
        self.finished = terminated
        return self._state(), reward, terminated, (not terminated) and self._truncated()

    def _truncated(self) -> bool:
        return self.time_elapsed >= self.MAX_EPISODE_TIME
