import math
from .route import Route as route_module
from .rider import Rider as rider_module
from . import wind as wind_module
# import matplotlib.pyplot as plt

MAX_CORNERING_VELOCITY = 100.0  #High improbable realistic number to avoid inf errors
CURVATURE_HALF_CHORD_M = 10.0   # Fit corner circles through points +/-10 m apart; ~1 m coordinate rounding then can't fake tight radii
MAX_BRAKE_DECEL = 4.0           # m/s^2 (~0.4 g), hard but controlled braking
SPIN_OUT_SPEED = 18.0           # m/s (~65 km/h), top gear at max cadence; no pedalling above this
DRIVETRAIN_EFFICIENCY = 0.975   # P_wheel = eta * P_pedal (chain + bearings)
ENVELOPE_SPACING_M = 5.0

def resistive_components(rider: rider_module, slope: float, v_rel: float, air_density: float) -> tuple[float, float, float]:
    theta = math.atan(slope / 100)

    gravity_force = rider.mass * 9.81 * math.sin(theta)
    rolling_resistance_force = rider.mass * 9.81 * rider.crr * math.cos(theta)
    # Signed drag: F = 0.5*rho*CdA*|v_rel|*v_rel. v_rel is the longitudinal relative
    # airspeed (headwind positive), so a tailwind faster than ground speed flips the
    # sign and drag becomes propulsive.
    drag_force = 0.5 * rider.cda * air_density * abs(v_rel) * v_rel

    return gravity_force, rolling_resistance_force, drag_force

def resistive_force(rider: rider_module, slope: float, v_rel: float, air_density: float) -> float:
    #Sum of gravity, drag resistance and rolling resistance forces
    gravity_force, rolling_resistance_force, drag_force = resistive_components(rider, slope, v_rel, air_density)
    return gravity_force + drag_force + rolling_resistance_force

def _to_local_xy(origin, point):
    #Convert geographic coordinates to local Cartesian coordinates
    lat0 = math.radians(origin[0])
    earth_radius = 6371000
    x = math.radians(point[1] - origin[1]) * math.cos(lat0) * earth_radius
    y = math.radians(point[0] - origin[0]) * earth_radius
    return x, y

def curvature_radius_at(route: route_module, distance_m: float):
    # Circle through points a chord's length behind and ahead (interpolated along the
    # route), not three neighbouring GPX points: the 3-point circle is exact for points
    # on a real corner, but on closely spaced points coordinate rounding dominates.
    total = route.total_distance()
    point_a = route.position_at(max(distance_m - CURVATURE_HALF_CHORD_M, 0.0))
    point_b = route.position_at(min(max(distance_m, 0.0), total))
    point_c = route.position_at(min(distance_m + CURVATURE_HALF_CHORD_M, total))

    #Calculate the curvature radius using the three points
    a = route_module.haversine_distance(point_b, point_c)
    b = route_module.haversine_distance(point_a, point_c)
    c = route_module.haversine_distance(point_a, point_b)

    xa, ya = 0.0, 0.0  # origin
    xb, yb = _to_local_xy(point_a, point_b)
    xc, yc = _to_local_xy(point_a, point_c)

    area = 0.5 * abs(xa * (yb - yc) + xb * (yc - ya) + xc * (ya - yb))

    if area == 0:
        return float('inf')  # Points are collinear, curvature radius is infinite

    radius = (a * b * c) / (4 * area)

    return radius


def max_cornering_velocity(route: route_module, distance_m: float, slope: float) -> float:
    #Calculate the maximum cornering velocity
    radius = curvature_radius_at(route, distance_m)

    if radius == float('inf'):
        return float(MAX_CORNERING_VELOCITY)

    friction_coefficient = 0.7  # Typical value for dry asphalt

    v_max = math.sqrt(friction_coefficient * math.cos(math.atan(slope / 100)) * 9.81 * radius)
    return v_max


def drive_force(rider: rider_module, velocity: float, p_target: float, resistive: float, dt: float) -> float:
    # Wheel force (N) such that F * v_new = P_wheel, i.e. power is applied at the
    # END-of-step speed. Evaluating F = P / v at the start-of-step speed blows up as
    # v -> 0 (F hits f_max and the step delivers several kW).
    #   v_new = v + (F - R) * dt / m_eff
    #   F * v_new = P  =>  (dt/m_eff) F^2 + (v - R dt/m_eff) F - P = 0, take the positive root.
    # As dt -> 0 this reduces to F = P / v.
    p_wheel = DRIVETRAIN_EFFICIENCY * p_target
    if p_wheel <= 0.0 or velocity >= SPIN_OUT_SPEED:
        return 0.0
    a = dt / rider.effective_mass
    b = velocity - resistive * a
    sqrt_disc = math.sqrt(b * b + 4.0 * a * p_wheel)
    # Two algebraically equal forms of the root; pick the one without cancellation.
    force = 2.0 * p_wheel / (b + sqrt_disc) if b >= 0.0 else (sqrt_disc - b) / (2.0 * a)
    return min(rider.f_max, force)


def braking_envelope(route: route_module, spacing_m: float = ENVELOPE_SPACING_M, decel: float = MAX_BRAKE_DECEL) -> list[float]:
    # Highest speed at each point k * spacing_m from which the rider can still brake down
    # to every cornering limit ahead. Backward pass from the finish:
    #   v_k = min(v_corner_k, sqrt(v_{k+1}^2 + 2 * a_net * ds))
    #   a_net = decel + g sin(theta)   (uphill helps braking, downhill hurts; drag ignored)
    total = route.total_distance()
    n = int(total // spacing_m) + 2
    envelope = [0.0] * n
    v_next = MAX_CORNERING_VELOCITY
    for k in reversed(range(n)):
        s = min(k * spacing_m, total)
        slope, *_ = route.slope_at(s)
        a_net = max(0.5, decel + 9.81 * math.sin(math.atan(slope / 100)))
        v_next = min(max_cornering_velocity(route, s, slope), math.sqrt(v_next ** 2 + 2 * a_net * spacing_m))
        envelope[k] = v_next
    return envelope


def envelope_speed_at(envelope: list[float], distance_m: float, spacing_m: float = ENVELOPE_SPACING_M) -> float:
    # Interpolate v^2 linearly between grid points: under constant deceleration
    # v^2 = v0^2 - 2 a ds, so this follows the braking curve exactly instead of
    # dropping a whole grid cell's worth of speed in one step.
    k = min(max(int(distance_m // spacing_m), 0), len(envelope) - 2)
    t = min(max(distance_m / spacing_m - k, 0.0), 1.0)
    return math.sqrt((1.0 - t) * envelope[k] ** 2 + t * envelope[k + 1] ** 2)


def advance_velocity(rider: rider_module, velocity: float, p_target: float, resistive: float, dt: float, v_limit: float = math.inf) -> tuple[float, float, bool]:
    # Force balance over one step, shared by step() and sim_manager: returns (new_velocity, drive, braking).
    # m_eff * dv/dt = F_drive - F_resistive; if that overshoots v_limit, stop pedalling and brake down to it.
    m_eff = rider.effective_mass

    drive = drive_force(rider, velocity, p_target, resistive, dt)
    new_velocity = velocity + (drive - resistive) / m_eff * dt

    braking = new_velocity > v_limit
    if braking:
        drive = 0.0
        new_velocity = min(velocity - resistive / m_eff * dt, v_limit)

    return max(0.0, new_velocity), drive, braking

def step(rider: rider_module, route: route_module, position: float, velocity: float, slope: float, v_rel: float, p_target: float, dt: float, air_density: float, break_force: float, v_limit: float = math.inf) -> tuple[float, float, float]:
    #Calculate the new velocity and position after a time step dt.
    # v_limit: speed the rider brakes down to (e.g. from braking_envelope). Leave at inf
    # when an agent controls braking itself and should face the cornering limit.

    gravity_force, rolling_force, drag_force = resistive_components(rider, slope, v_rel, air_density)
    resistive = gravity_force + rolling_force + drag_force + break_force

    new_velocity, drive, _ = advance_velocity(rider, velocity, p_target, resistive, dt, v_limit)

    p_realized = drive * new_velocity / DRIVETRAIN_EFFICIENCY  # Pedal power; equals p_target unless f_max-limited

    position += new_velocity * dt  # Update position

    return position, new_velocity, p_realized



def simulate(rider: rider_module, route: route_module, wind_velocity_vector: tuple[float, float], p_target: float, dt: float, air_density: float) -> tuple[list[dict], float]:
    #Simulate the ride along the route with given wind conditions and target power
    results = []
    position = 0.0
    velocity = 0.0
    total_distance = route.total_distance()
    mechanical_joules = 0.0

    max_time = 3600 * 3  # 3 hours
    time_elapsed = 0.0
    envelope = braking_envelope(route)

    while position < total_distance and time_elapsed < max_time:
        slope, ele1, ele2, cum_dist1, cum_dist2 = route.slope_at(position) if position is not None else (0.0, 0.0, 0.0, 0.0, 0.0)

        heading = route.heading_at(position) if position is not None else 0.0

        math_angle = math.pi / 2 - heading
        bike_velocity_vector = (velocity * math.cos(math_angle), velocity * math.sin(math_angle))

        apparent_wind_speed, yaw_angle = wind_module.apparent_wind(bike_velocity_vector, wind_velocity_vector, heading)
        v_rel = wind_module.longitudinal_airspeed(heading, velocity, wind_velocity_vector)

        v_limit = envelope_speed_at(envelope, position)
        max_velocity = max_cornering_velocity(route, position, slope)  # cornering limit at the start of the step, for the output
        position, velocity, p_realized = step(rider, route, position, velocity, slope, v_rel, p_target, dt, air_density, 0.0, v_limit)

        mechanical_joules += p_realized * dt  # Accumulate mechanical energy

        # print(f"Position: {position:.2f} m, Velocity: {velocity:.2f} m/s, Slope: {slope:.2f} %, Apparent Wind Speed: {apparent_wind_speed:.2f} m/s, Yaw Angle: {yaw_angle:.2f} degrees, Max Speed: {max_velocity:.2f} m/s")

        results.append((position, velocity, slope, apparent_wind_speed, yaw_angle, max_velocity, p_realized, ele1, ele2, cum_dist1, cum_dist2))  # Store position and velocity

        time_elapsed += dt

    metabolic_joules = mechanical_joules / rider.metabolic_efficiency  # Calculate total metabolic energy based on efficiency
    kcal_burned = metabolic_joules / 4184  # Convert joules to kilocalories

    return results, kcal_burned


# def velocity_position_graph(results: tuple[list[dict], float]):
#     plt.plot([r[0] for r in results[0]], [r[1] for r in results[0]])
#     plt.xlabel("Position (m)")
#     plt.ylabel("Velocity (m/s)")
#     plt.title("Simulation Results")
#     plt.savefig("velocity_chart_results.png")


# def slope_position_graph(results: tuple[list[dict], float]):
#     plt.plot([r[0] for r in results[0]], [r[2] for r in results[0]])
#     plt.xlabel("Position (m)")
#     plt.ylabel("Slope (%)")
#     plt.title("Slope vs Position")
#     plt.savefig("slope_chart_results.png")


# if __name__ == "__main__":
#     # Example usage
#     rider = rider_module(rider_mass=70, bike_mass=10, ftp=250, f_max=1000, cda=0.3, crr=0.005, inertia=1.0, wheel_radius=0.35, metabolic_efficiency=0.22)
#     route = route_module.get_route_from_gpx("../data/encinitas.gpx")  # Load a route from a GPX file
#     #route = route_module.get_route_from_gpx("../data/tour-de-friends.gpx")  # Load a route from a GPX file
#     wind_velocity_vector = (5.0, 0.0)  # Wind blowing from the west at 5 m/s
#     p_target = 200.0  # Target power in watts
#     dt = 0.1  # Time step in seconds

#     results = simulate(rider, route, wind_velocity_vector, p_target, dt)

#     with open("simulation_results.txt", "w") as f:
#         for position, velocity, slope, apparent_wind_speed, yaw_angle, max_velocity, p_realized, ele1, ele2, cum_dist1, cum_dist2 in results[0]:
#             f.write(f"Position: {position:.2f} m, Velocity: {velocity:.2f} m/s, Slope: {slope:.2f} %, Apparent Wind Speed: {apparent_wind_speed:.2f} m/s, Yaw Angle: {yaw_angle:.2f} degrees, Max Speed: {max_velocity:.2f} m/s, Realized Power: {p_realized:.2f} W, Elevation 1: {ele1:.2f} m, Elevation 2: {ele2:.2f} m, Cumulative Distance 1: {cum_dist1:.2f} m, Cumulative Distance 2: {cum_dist2:.2f} m\n")
#         f.write(f"Total kcal burned: {results[1]:.2f} kcal\n")

#     velocity_position_graph(results)
#     slope_position_graph(results)
#     route.get_route_profile()  # Display the route profile