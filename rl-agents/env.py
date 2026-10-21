import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import math
from collections import deque
from backend.engine import optimizer, physics
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
    # Reward per joule of W' gained (+) or spent (-), on the TIME_PENALTY scale. The DP value
    # function puts 1 kJ of W' at ~1-3 s of ride time on stage-1 (more on the climbs), so 2 s/kJ.
    # The agent then spends W' only where it buys more than 2 s/kJ: climbs (~3 s/kJ at 8 %),
    # not fast descents (~0.7 s/kJ at -4 %, drag ~ v^2), where riding below CP refills it instead.
    W_PRIME_VALUE = 2.0e-3 * TIME_PENALTY
    OVERSPEED_PENALTY = 20.0  # per m/s above the braking envelope, per step: the warning comes while braking can still help, not only at the crash
    LIMIT_SPACING_M = physics.ENVELOPE_SPACING_M  # speed-limit grid, shared by observation and crash check
    CURVE_HORIZON_M = 500.0
    CURVE_SPEED_CAP = 30.0  # m/s; grid points with a higher limit don't count as curves
    CLIMB_HORIZON_M = 1000.0  # climbing-ahead observation: ascent over this far ahead
    CLIMB_SCALE_M = 50.0      # ascent normalisation (stage-1: up to ~37 m in any 1 km)
    ENVELOPE_MARGIN = 0.97  # braking envelope aims at 97 % of each cornering limit: leaves ~1/3 of grip to brake in the bend

    def __init__(self, rider: rider_module.Rider, route: route_module.Route, wind_velocity_vector: tuple[float, float] = (0.0, 0.0), dt: float | None = None,
                 value_function: list | None = None, gamma: float = 0.99):
        # value_function: DP time-to-go tables (optimizer.solve, under this env's envelope). Given,
        # the reward is shaped with a potential instead of the flat W' price:
        #   r' = r + gamma Phi(s') - Phi(s),   Phi = -(V(s, v, W') - min_{v,W'} V(s, ., .)),   Phi(terminal) = 0
        # Phi = seconds behind the best state at this point of the route. Not Phi = -V: that makes
        # Q' = Q + V_DP (0..1000 s) and adds ~0.01 V per step, burying the ~0.1 s action gaps;
        # the run-dpshape agent then braked at a standstill (+9.7/step vs +10.2 for riding).
        # Potential-based shaping leaves the optimal policy unchanged (Ng et al. 1999) when gamma is
        # the agent's discount, and it prices W' (and speed) by what they're worth HERE: ~3 s/kJ
        # before a steep climb, far less before a descent, where the flat 2 s/kJ got both wrong.
        self.value_function = value_function
        self.gamma = gamma
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
        self._precompute_ascent()

        self.n_power = len(self.POWER_SPACE)
        self.n_brake = len(self.BRAKE_SPACE)
        self.n_actions = self.n_power + self.n_brake

        self.n_state = 13

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
        self._compute_braking_envelope()

    def _precompute_ascent(self):
        # Cumulative climbing (m) up to each grid point, from the route's smoothed elevation; only
        # rises count. Ascent over [s, s + h] = cum[k(s + h)] - cum[k(s)].
        ds = self.LIMIT_SPACING_M
        n = int(self.total_distance // ds) + 2
        ele = [self.route.position_at(min(k * ds, self.total_distance))[2] for k in range(n)]
        self.cum_ascent = [0.0]
        for k in range(1, n):
            self.cum_ascent.append(self.cum_ascent[-1] + max(ele[k] - ele[k - 1], 0.0))

    def _ascent_ahead(self) -> float:
        # Metres of climbing in the next CLIMB_HORIZON_M. The grade look-ahead stops at 200 m, so
        # without this the agent couldn't save W' for a climb it can't see yet (it reached the
        # 11 % ramp at 6.3 km with W' = 0 after spending it on the flat before).
        ds, last = self.LIMIT_SPACING_M, len(self.cum_ascent) - 1
        k0 = min(int(self.position // ds), last)
        k1 = min(int((self.position + self.CLIMB_HORIZON_M) // ds), last)
        return self.cum_ascent[k1] - self.cum_ascent[k0]

    def _potential(self, terminal: bool = False) -> float:
        # Phi = -(seconds the current (speed, W') loses to the best state at this position, by the DP); 0 at the finish.
        if terminal:
            return 0.0
        return -optimizer.value_at(self.value_function, self.position, self.velocity, self.w_prime_balance, behind_best=True)

    def _compute_braking_envelope(self):
        # envelope[k]: fastest the rider may pass grid point k and still, braking as hard as the
        # tyres allow, stay under every cell limit ahead (m/s). Backward pass like
        # physics.braking_envelope, but with this env's rules:
        #   - point k ends cell k-1 and starts cell k, each limited by the lower of its two ends,
        #     times ENVELOPE_MARGIN (at exactly the limit no grip is left to brake against gravity);
        #   - brake force = strongest action (500 N), cut by the friction circle in a bend:
        #       F <= mu m g cos(theta) sqrt(1 - (v / v_cell)^4)   (same rule as _grip_left_factor),
        #     kept 20 % inside the edge (room for the 50 N brake steps); braking in a bend near its limit is barely possible;
        #   - a = (F + m g sin(theta) + rolling) / m_eff: a descent eats into braking (drag ignored,
        #     it only helps), so on a steep descent the bend can force the speed down earlier.
        #   v_k = min(v_cap, sqrt(v_{k+1}^2 + 2 a ds)), with a evaluated at v_k (a few fixed-point
        #   iterations: less speed in the bend leaves more grip for braking).
        ds = self.LIMIT_SPACING_M
        limits = self.speed_limits
        n = len(limits)
        m, m_eff = self.rider.mass, self.rider.effective_mass
        f_max = max(self.BRAKE_SPACE)
        self.envelope = [0.0] * n
        v_next = physics.MAX_CORNERING_VELOCITY
        for k in reversed(range(n)):
            cell = min(limits[k], limits[min(k + 1, n - 1)])
            v_cap = self.ENVELOPE_MARGIN * min(cell, limits[max(k - 1, 0)])
            theta = math.atan(self._slope_at(k * ds) / 100)
            grip_n = physics.FRICTION_COEFFICIENT * 9.81 * math.cos(theta) * m
            resist = m * 9.81 * (math.sin(theta) + self.rider.crr * math.cos(theta))
            v = v_cap
            for _ in range(4):
                f = min(f_max, 0.8 * grip_n * math.sqrt(max(1.0 - (v / cell) ** 4, 0.0)))
                v = min(v_cap, math.sqrt(max(v_next ** 2 + 2.0 * (f + resist) / m_eff * ds, 0.0)))
            self.envelope[k] = v_next = v

    def _speed_limit_over(self, s0: float, s1: float) -> float:
        # Lowest limit over every grid cell the stretch [s0, s1] touches (limit inside a cell =
        # the lower of its two end points). One step can cover several cells (20 m/s * 0.5 s =
        # 10 m = 2 cells), so checking only the start cell lets the rider skip past corners.
        last = len(self.speed_limits) - 2
        k0 = min(max(int(s0 // self.LIMIT_SPACING_M), 0), last)
        k1 = min(max(int(s1 // self.LIMIT_SPACING_M), k0), last)
        return min(self.speed_limits[k0:k1 + 2])

    def _binding_curve_ahead(self):
        # The curve within the horizon that limits the current speed most: the one with the lowest
        #   v_allow_k = sqrt(v_k^2 + 2 a_max d_k)   (fastest you can go now and still brake in time)
        # Ranking by a_req = (v^2 - v_k^2) / (2 d) instead breaks below every limit: all a_req are
        # negative and dividing by a large d pulls far curves toward 0, so a limit 0.3 m/s above
        # the rider in its own cell lost to a curve 350 m away and the agent rode into it.
        # Starts at the cell the rider is in, so the current limit is always a candidate.
        # Measured the way the crash check sees limits: cell k spans [k ds, (k+1) ds] with limit
        # min(L_k, L_k+1), so a limit binds from the START of the cell before its grid point.
        # Braking deceleration counts the resistance on the current grade (less on descents).
        # Distance in v_allow is d_eff = d - v dt: "can I still make it after one more step?"
        # At 16.5 m/s a 6.8 m/s corner 25 m ahead is brakeable now (v_allow 18 m/s) but not after
        # the next 8 m, so ranking on d hid it until it was too late. All limits within one step
        # get d_eff = 0, so the lowest of them binds.
        # Returns (distance_m, limit_mps) for that curve, or None if no curve is in range.
        ds = self.LIMIT_SPACING_M
        last = len(self.speed_limits) - 2
        k0 = min(max(int(self.position // ds), 0), last)
        k1 = min(int((self.position + self.CURVE_HORIZON_M) // ds), last)
        a_max = max((max(self.BRAKE_SPACE) + self._resistive_force()) / self.rider.effective_mass, 0.5)
        lead = self.velocity * self.DT
        best = None
        best_v_allow2 = math.inf
        for k in range(k0, k1 + 1):
            limit = min(self.speed_limits[k], self.speed_limits[k + 1])
            if limit >= self.CURVE_SPEED_CAP:
                continue
            dist = max(k * ds - self.position, 0.0)
            v_allow2 = limit ** 2 + 2.0 * a_max * max(dist - lead, 0.0)
            if v_allow2 < best_v_allow2:
                best_v_allow2 = v_allow2
                best = (dist, limit)
        return best

    def _envelope_over_step(self) -> float:
        # Lowest envelope speed wherever this step can end, [s, s + (v + 2 m/s) dt] (m/s). The crash
        # check holds the END speed to the cell the step ends in, and pedalling carries the rider a
        # bit further than v dt, where the envelope can already have dropped into a corner cell.
        ds = self.LIMIT_SPACING_M
        s0 = self.position
        s1 = s0 + (self.velocity + 2.0) * self.DT
        v_min = min(physics.envelope_speed_at(self.envelope, s0, ds), physics.envelope_speed_at(self.envelope, s1, ds))
        last = len(self.envelope) - 1
        for k in range(min(int(s0 // ds) + 1, last), min(int(s1 // ds), last) + 1):
            v_min = min(v_min, self.envelope[k])
        return v_min

    def _resistive_force(self) -> float:
        # Gravity + rolling + drag at the current state (N), as physics.step computes it; > 0 slows.
        position = min(self.position, self.total_distance)
        slope = self._slope_at(position)
        v_rel = wind_module.longitudinal_airspeed(self.route.heading_at(position), self.velocity, self.wind_velocity_vector)
        rho = physics.air_density_at(self.AIR_DENSITY, self.route.position_at(position)[2])
        return physics.resistive_force(self.rider, slope, v_rel, rho)

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
            dist_to_curve, curve_max_speed = upcoming
            dist_to_curve = min(dist_to_curve, self.CURVE_HORIZON_M) / self.CURVE_HORIZON_M
            curve_max_speed = curve_max_speed / 30.0
        else:
            dist_to_curve = 1.0
            curve_max_speed = 1.0

        # Brake force needed THIS step to end it on the braking envelope, after resistance does its part:
        #   a = (v - v_env) / dt,  F_req = m_eff a - F_resist  (N),  brake_need = F_req / 500 N
        # 1.0 = the hardest brake action, 0 = coasting is exactly enough (on a descent that needs
        # braking even to hold speed), negative = room to pedal. Clipped to +/-2.
        # The envelope includes the friction circle, so braking early enough is visible here: a
        # single "binding curve + full brake" number hid that a bend leaves little grip to brake.
        v_env = self._envelope_over_step()
        f_req = self.rider.effective_mass * (self.velocity - v_env) / self.DT - self._resistive_force()
        brake_need = min(max(f_req / max(self.BRAKE_SPACE), -2.0), 2.0)
        self._recent_brake_need.append(brake_need)  # diagnostics only (crash_log)

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
            self._ascent_ahead() / self.CLIMB_SCALE_M,
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
        self.crash_log = []  # one dict per crash, for diagnosing *why* the agent crashes
        self._recent_brake_need = deque(maxlen=max(1, round(2.0 / self.DT)))  # last ~2 s of observed brake need
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

    def _simulate(self, position: float, velocity: float, p_target: float, brake_force: float):
        # One physics step from (position, velocity) without touching env state.
        # Returns (new_position, new_velocity, p_realized, crashed).
        slope = self._slope_at(position)
        heading = self.route.heading_at(position)
        v_rel = wind_module.longitudinal_airspeed(heading, velocity, self.wind_velocity_vector)

        # No v_limit: the agent must brake for corners itself or crash
        new_position, new_velocity, p_realized = physics.step(
            rider=self.rider,
            route=self.route,
            position=position,
            velocity=velocity,
            slope=slope,
            v_rel=v_rel,
            p_target=p_target,
            dt=self.DT,
            air_density=self.AIR_DENSITY,
            break_force=brake_force,
        )
        # The step covers [start, new_position] at new_velocity (position += v_new * dt), so that
        # speed must respect every limit on the way, not just the one where the step started.
        limit = self._speed_limit_over(position, new_position) * self._grip_left_factor(brake_force, slope)
        return new_position, new_velocity, p_realized, new_velocity > limit

    def step(self, action: int):
        """Returns (state, reward, terminated, truncated)."""
        p_target, brake_force = self.action_index_to_values(action)
        # Can't ride above CP for longer than W' allows: cap so this step can't overdraw it
        p_target = min(p_target, self.critical_power + self.w_prime_balance / self.DT)

        slope = self._slope_at(self.position)
        start_position = self.position
        shaping = self.value_function is not None
        phi_before = self._potential() if shaping else 0.0

        new_position, new_velocity, p_realized, crashed = self._simulate(self.position, self.velocity, p_target, brake_force)

        self.time_elapsed += self.DT
        self.mechanical_joules += p_realized * self.DT
        w_before = self.w_prime_balance
        self._update_w_prime(p_realized)
        # Price W' at what it's worth in ride time: refilling earns, spending costs, both NOW.
        # Recharging on a descent only pays off on a climb minutes later, far beyond the agent's
        # gamma = 0.99 horizon (~50 s), so it burned W' in the first 2 min and never refilled it.
        # With DP shaping the potential prices W' instead.
        w_price = 0.0 if shaping else self.W_PRIME_VALUE * (self.w_prime_balance - w_before)

        if crashed:
            limit = self._speed_limit_over(start_position, new_position)
            grip_factor = self._grip_left_factor(brake_force, slope)
            # Crash before the corner: lose the speed (and the time to regain it) plus a fixed penalty.
            # Not terminal, so ending the episode early is never an escape from time penalties.
            self.crashes += 1
            self.crash_log.append({
                "position_m": start_position,
                "time_s": self.time_elapsed,
                "grade_pct": slope,
                "v_before": self.velocity,             # m/s, at the start of the step
                "v_new": new_velocity,                 # m/s, speed that broke the limit
                "limit": limit,                        # m/s, cornering limit without braking
                "grip_factor": grip_factor,            # < 1 when braking used up grip
                "overshoot": new_velocity - limit * grip_factor,  # m/s over the effective limit
                "power_w": p_target,
                "brake_n": brake_force,
                "brake_need": list(self._recent_brake_need),  # oldest -> newest, ~2 s before the crash
            })
            self.velocity = 0.0
            reward = -self.CRASH_PENALTY - self.TIME_PENALTY * self.DT + w_price
            if shaping:  # speed reset to 0: the potential also charges the time to get going again
                reward += self.gamma * self._potential() - phi_before
            return self._state(), reward, False, self._truncated()

        self.position, self.velocity = new_position, new_velocity

        # Minimise finishing time. Progress reward is shaping: it sums to the same
        # constant for every finished ride, so only the time term ranks policies.
        reward = self.PROGRESS_REWARD * (min(self.position, self.total_distance) - start_position) - self.TIME_PENALTY * self.DT
        # Above the braking envelope = braked too late for a curve ahead, even if the crash is still
        # a few steps away. Penalising it here gives a signal before the crash; a rider who brakes
        # in time (ends each step at or below the envelope) never pays it.
        overspeed = self.velocity - physics.envelope_speed_at(self.envelope, min(self.position, self.total_distance), self.LIMIT_SPACING_M)
        reward -= self.OVERSPEED_PENALTY * max(overspeed, 0.0)
        reward += w_price

        terminated = self.position >= self.total_distance
        self.finished = terminated
        if shaping:
            reward += self.gamma * self._potential(terminal=terminated) - phi_before
        elif terminated:
            # W' left at the finish is worth nothing. With this, the W' terms sum to
            # -W_PRIME_VALUE * W'_start over every finished ride (undiscounted), the same for all
            # policies, so ride time alone still ranks them; without it, the agent would be paid
            # for finishing with W' unspent.
            reward -= self.W_PRIME_VALUE * self.w_prime_balance
        return self._state(), reward, terminated, (not terminated) and self._truncated()

    def _grip_left_factor(self, brake_force: float, slope: float) -> float:
        # Friction circle: braking uses tyre grip the corner then can't have.
        #   (v^2 / R)^2 + a_b^2 <= (mu g cos(theta))^2,  a_b = F_brake / m
        # and v_max^4 = (mu g cos(theta) R)^2, so the cornering limit while braking shrinks to
        #   v_max(F) = v_max * (1 - (a_b / (mu g cos(theta)))^2)^(1/4)
        # Full brake (500 N, 80 kg) on the flat: factor 0.64. Grip uses plain mass (tyre load).
        if brake_force <= 0.0:
            return 1.0
        grip = physics.FRICTION_COEFFICIENT * 9.81 * math.cos(math.atan(slope / 100))
        used = brake_force / self.rider.mass / grip
        return max(1.0 - used ** 2, 0.0) ** 0.25

    def _truncated(self) -> bool:
        return self.time_elapsed >= self.MAX_EPISODE_TIME
