import math
import threading
import uuid
from datetime import datetime, timezone

import engine.physics as physics
import engine.wind as wind
from engine.rider import Rider
from engine.route import Route
from schemas import (
    RiderConfig,
    SegmentResult,
    SimConfigPayload,
    SimSummary,
    TelemetryPoint,
)

MAX_SUBSTEP_S = 0.1
MAX_SIM_TIME_S = 24 * 3600
STALL_TICKS_LIMIT = 5


def rider_from_config(cfg: RiderConfig) -> Rider:
    return Rider(
        rider_mass=cfg.mass,
        bike_mass=0.0,
        ftp=cfg.ftp,
        f_max=max(50.0, cfg.ftp * 6.0),
        cda=cfg.cda,
        crr=cfg.crr,
        inertia=1.0,
        wheel_radius=0.35,
        metabolic_efficiency=0.22,
    )


class SimulationSession:
    def __init__(self, sim_id: str, rider: Rider, route: Route, config: SimConfigPayload):
        self.id = sim_id
        self.rider = rider
        self.route = route
        self.config = config
        self.total_distance_m = route.total_distance()
        self.status = "running"
        self.stop_reason = None
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.t = 0.0
        self.position_m = 0.0
        self.velocity = 0.0
        self.mechanical_joules = 0.0
        self._stall_ticks = 0
        self._history: list[TelemetryPoint] = []
        self._lock = threading.Lock()

    @property
    def history(self) -> list[TelemetryPoint]:
        return self._history

    @property
    def kcal_burned(self) -> float:
        metabolic_joules = self.mechanical_joules / max(1e-6, self.rider.metabolic_efficiency)
        return metabolic_joules / 4184

    def pause(self):
        with self._lock:
            if self.status == "running":
                self.status = "paused"

    def resume(self):
        with self._lock:
            if self.status == "paused":
                self.status = "running"

    def stop(self, reason: str | None = None):
        with self._lock:
            if self.status not in ("complete", "stopped"):
                self.status = "stopped"
                self.stop_reason = reason or "Stopped by client"

    def restart(self):
        with self._lock:
            self.status = "running"
            self.stop_reason = None
            self.t = 0.0
            self.position_m = 0.0
            self.velocity = 0.0
            self.mechanical_joules = 0.0
            self._stall_ticks = 0
            self._history.clear()

    def _substep(self, h: float) -> dict:
        env = self.config.environment
        p_target = self.config.strategy.targetPower

        slope_pct, _, _, _, _ = self.route.slope_at(min(self.position_m, self.total_distance_m))

        bike_velocity_vector = (self.velocity, 0.0)
        wind_vector = wind.wind_vector_from_bearing(env.windSpeed, env.windBearing)
        apparent_wind_speed, yaw_angle = wind.apparent_wind(bike_velocity_vector, wind_vector)

        grav_force, rolling_force, aero_force = physics.resistive_components(
            self.rider, slope_pct, apparent_wind_speed, env.airDensity
        )
        resistive = grav_force + rolling_force + aero_force

        drive = physics.drive_force(self.rider, max(self.velocity, 1e-3), p_target)
        acceleration = (drive - resistive) / self.rider.mass

        v_raw = self.velocity + acceleration * h
        v_max_corner = physics.max_cornering_velocity(self.route, self.position_m, slope_pct)

        clamped = v_raw > v_max_corner
        v_new = min(max(v_raw, 0.0), v_max_corner)

        if clamped:
            realized_power = 0.0
            limit_reason = f"Cornering limit {v_max_corner:.1f} m/s — coasting"
        else:
            realized_power = drive * self.velocity
            limit_reason = None

        self.position_m += v_new * h
        self.velocity = v_new
        self.mechanical_joules += realized_power * h

        _, _, elevation = self.route.position_at(min(self.position_m, self.total_distance_m))

        return {
            "slope_pct": slope_pct,
            "grav_force": grav_force,
            "rolling_force": rolling_force,
            "aero_force": aero_force,
            "apparent_wind_speed": apparent_wind_speed,
            "yaw_angle": yaw_angle,
            "elevation": elevation,
            "clamped": clamped,
            "limit_reason": limit_reason,
            "drive": drive,
        }

    def tick(self) -> TelemetryPoint | None:
        with self._lock:
            if self.status != "running":
                return self._history[-1].model_copy(deep=True) if self._history else None

            dt = self.config.simSettings.timeStepS
            n_substeps = max(1, math.ceil(dt / MAX_SUBSTEP_S - 1e-9))
            h = dt / n_substeps

            joules_start = self.mechanical_joules
            last = None
            force_limited = False
            limit_reason = None

            for _ in range(n_substeps):
                last = self._substep(h)
                if last["clamped"]:
                    force_limited = True
                    limit_reason = last["limit_reason"]

            joules_tick = self.mechanical_joules - joules_start
            self.t += dt

            if self.position_m >= self.total_distance_m:
                self.position_m = self.total_distance_m
                self.status = "complete"
            elif self.velocity < 0.05 and last["drive"] <= last["grav_force"]:
                self._stall_ticks += 1
                if self._stall_ticks >= STALL_TICKS_LIMIT:
                    self.status = "stopped"
                    self.stop_reason = f"Rider cannot overcome gradient of {last['slope_pct']:.1f}%"
            else:
                self._stall_ticks = 0

            if self.t >= MAX_SIM_TIME_S:
                self.status = "stopped"
                self.stop_reason = "Maximum simulated time exceeded"

            point = TelemetryPoint(
                t=self.t,
                dist=self.position_m / 1000,
                speed=self.velocity,
                targetPower=self.config.strategy.targetPower,
                realizedPower=joules_tick / dt,
                elevation=last["elevation"],
                grade=last["slope_pct"],
                gravForce=last["grav_force"],
                rollingForce=last["rolling_force"],
                aeroForce=last["aero_force"],
                totalEnergy=self.mechanical_joules / 1000,
                forceLimited=force_limited,
                limitReason=limit_reason,
                kcalBurned=self.kcal_burned,
            )
            self._history.append(point)
            return point

    def summary(self) -> SimSummary:
        hist = self._history
        empty = SimSummary(
            totalTimeS=0, totalDistKm=0, avgSpeedKph=0, avgRealizedPower=0,
            maxSpeedKph=0, totalEnergyKj=0, avgGrade=0, normPower=0,
            kcalBurned=0, stopReason=self.stop_reason, segments=[],
        )
        if len(hist) < 2:
            return empty

        last_point = hist[-1]
        total_time_s = last_point.t
        total_dist_km = last_point.dist

        avg_speed_kph = total_dist_km / (total_time_s / 3600) if total_time_s > 0 else 0.0
        avg_realized_power = sum(p.realizedPower for p in hist) / len(hist)
        max_speed_kph = max(p.speed for p in hist) * 3.6
        avg_grade = sum(p.grade for p in hist) / len(hist)
        norm_power = (sum(p.realizedPower ** 4 for p in hist) / len(hist)) ** 0.25

        segments: list[SegmentResult] = []
        seg_count = 3
        seg_size = len(hist) // seg_count
        seg_names = ["Opening Sector", "Climb / Mid-Race", "Final Sector"]
        for s in range(seg_count):
            start = s * seg_size
            end = (s + 1) * seg_size if s < seg_count - 1 else len(hist)
            slice_ = hist[start:end]
            if len(slice_) < 2:
                continue
            segments.append(SegmentResult(
                name=seg_names[s],
                distStartKm=slice_[0].dist,
                distEndKm=slice_[-1].dist,
                avgSpeedKph=sum(p.speed for p in slice_) / len(slice_) * 3.6,
                avgRealizedPower=sum(p.realizedPower for p in slice_) / len(slice_),
                avgGrade=sum(p.grade for p in slice_) / len(slice_),
                timeS=slice_[-1].t - slice_[0].t,
            ))

        return SimSummary(
            totalTimeS=total_time_s,
            totalDistKm=total_dist_km,
            avgSpeedKph=avg_speed_kph,
            avgRealizedPower=avg_realized_power,
            maxSpeedKph=max_speed_kph,
            totalEnergyKj=last_point.totalEnergy,
            avgGrade=avg_grade,
            normPower=norm_power,
            kcalBurned=last_point.kcalBurned,
            stopReason=self.stop_reason,
            segments=segments,
        )


class SimulationManager:
    def __init__(self):
        self._sessions: dict[str, SimulationSession] = {}
        self._lock = threading.Lock()

    def create(self, rider: Rider, route: Route, config: SimConfigPayload) -> SimulationSession:
        sim_id = f"sim-{uuid.uuid4().hex[:12]}"
        session = SimulationSession(sim_id, rider, route, config)
        with self._lock:
            self._sessions[sim_id] = session
        return session

    def get(self, sim_id: str) -> SimulationSession | None:
        return self._sessions.get(sim_id)

    def delete(self, sim_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(sim_id, None) is not None


manager = SimulationManager()
