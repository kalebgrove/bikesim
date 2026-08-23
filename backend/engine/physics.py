import math
from engine.route import Route as route_module
from engine.rider import Rider as rider_module
import engine.wind as wind_module
# import matplotlib.pyplot as plt

MAX_CORNERING_VELOCITY = 100.0  #High improbable realistic number to avoid inf errors

def resistive_components(rider: rider_module, slope: float, apparent_wind_speed: float, air_density: float) -> tuple[float, float, float]:
    theta = math.atan(slope / 100)

    gravity_force = rider.mass * 9.81 * math.sin(theta)
    rolling_resistance_force = rider.mass * 9.81 * rider.crr * math.cos(theta)
    drag_force = 0.5 * rider.cda * air_density * apparent_wind_speed ** 2

    return gravity_force, rolling_resistance_force, drag_force

def resistive_force(rider: rider_module, slope: float, apparent_wind_speed: float, air_density: float) -> float:
    #Sum of gravity, drag resistance and rolling resistance forces
    gravity_force, rolling_resistance_force, drag_force = resistive_components(rider, slope, apparent_wind_speed, air_density)
    return gravity_force + drag_force + rolling_resistance_force

def _to_local_xy(origin, point):
    #Convert geographic coordinates to local Cartesian coordinates
    lat0 = math.radians(origin[0])
    earth_radius = 6371000
    x = math.radians(point[1] - origin[1]) * math.cos(lat0) * earth_radius
    y = math.radians(point[0] - origin[0]) * earth_radius
    return x, y

def curvature_radius_at(route: route_module, distance_m: float):
    i, j = route._bracketing_indexes(distance_m)

    point_a = route.points[i] if i >= 0 else route.points[0]
    point_b = route.points[j] if j < len(route.points) else route.points[-1]
    point_c = route.points[j + 1] if j + 1 < len(route.points) else route.points[-1]

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


def drive_force(rider: rider_module, velocity: float, p_target: float, epsilon=1e-3) -> float:
    #calculate the drive force based on the target power and current velocity
    
    return min(rider.f_max, p_target / max(epsilon, velocity))  # Ensure the drive force does not exceed the maximum force


def step(rider: rider_module, route: route_module, position: float, velocity: float, slope: float, apparent_wind_speed: float, p_target: float, dt: float, air_density: float) -> tuple[float, float, float, float]:
    #Calculate the new velocity and position after a time step dt

    resistive = resistive_force(rider, slope, apparent_wind_speed, air_density)
    drive = drive_force(rider, velocity, p_target)

    net_force = drive - resistive
    acceleration = net_force / rider.mass

    max_velocity = max_cornering_velocity(route, position, slope)

    velocity = min(velocity + acceleration * dt, max_velocity)  # Update velocity, but don't exceed the maximum cornering velocity

    p_realized = drive * velocity  # Calculate the realized power based on the drive force and current velocity

    position += velocity * dt  # Update position

    return position, velocity, max_velocity, p_realized



def simulate(rider: rider_module, route: route_module, wind_velocity_vector: tuple[float, float], p_target: float, dt: float, air_density: float) -> tuple[list[dict], float]:
    #Simulate the ride along the route with given wind conditions and target power
    results = []
    position = 0.0
    velocity = 0.0
    total_distance = route.total_distance()
    mechanical_joules = 0.0

    max_time = 3600 * 3  # 3 hours
    time_elapsed = 0.0

    while position < total_distance and time_elapsed < max_time:
        slope, ele1, ele2, cum_dist1, cum_dist2 = route.slope_at(position) if position is not None else (0.0, 0.0, 0.0, 0.0, 0.0)

        heading = route.heading_at(position) if position is not None else 0.0

        math_angle = math.pi / 2 - heading
        bike_velocity_vector = (velocity * math.cos(math_angle), velocity * math.sin(math_angle))

        apparent_wind_speed, yaw_angle = wind_module.apparent_wind(bike_velocity_vector, wind_velocity_vector)

        position, velocity, max_velocity, p_realized = step(rider, route, position, velocity, slope, apparent_wind_speed, p_target, dt, air_density)

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