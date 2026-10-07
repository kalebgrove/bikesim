import math

def wind_vector_from_bearing(wind_speed: float, bearing_deg: float) -> tuple[float, float]:
    # World-frame air velocity (east, north) in m/s for wind blowing FROM the given
    # compass bearing (degrees clockwise from north, matching route headings).
    # Meteorological convention: a 0 deg (northerly) wind blows toward the south.
    b = math.radians(bearing_deg)
    return (-wind_speed * math.sin(b), -wind_speed * math.cos(b))


def longitudinal_airspeed(heading: float, velocity: float, wind_velocity_vector: tuple[float, float]) -> float:
    """Signed relative airspeed along the direction of travel (m/s).

    heading: bearing in radians, clockwise from north (as returned by Route.heading_at).
    velocity: ground speed (m/s).
    wind_velocity_vector: world-frame air velocity (east, north) in m/s.

    v_rel = v_ground - (wind . heading_unit)
          = v_ground + wind_speed * cos(from_bearing - heading)

    Positive => air approaches from the front (adds drag); negative => net tailwind
    exceeds ground speed, so aero drag becomes propulsive.
    """
    h = (math.sin(heading), math.cos(heading))  # unit travel direction (east, north)
    wind_along_travel = wind_velocity_vector[0] * h[0] + wind_velocity_vector[1] * h[1]
    return velocity - wind_along_travel

def apparent_wind(bike_velocity_vector, wind_velocity_vector, heading: float) -> tuple[float, float]:
    """
    Calculate the apparent wind speed and yaw angle based on the bike's velocity and the wind's velocity.

    Parameters:
    bike_velocity_vector (tuple): A tuple containing the bike's velocity components (east, north).
    wind_velocity_vector (tuple): A tuple containing the wind's velocity components (east, north).
    heading (float): Direction of travel in radians, clockwise from north.

    Returns:
    tuple: Apparent wind speed (m/s) and yaw angle in degrees relative to the direction of
    travel: 0 = air from straight ahead, +90 = from the right, +/-180 = from behind.
    """
    # Calculate the apparent wind vector (air velocity as the rider feels it)
    apparent_wind_vector = (wind_velocity_vector[0] - bike_velocity_vector[0],
                            wind_velocity_vector[1] - bike_velocity_vector[1])

    # Calculate the magnitude of the apparent wind vector
    apparent_wind_speed = math.sqrt(apparent_wind_vector[0] ** 2 + apparent_wind_vector[1] ** 2)

    # Compass bearing the air comes FROM (opposite of where it moves), then relative to heading
    from_bearing = math.atan2(-apparent_wind_vector[0], -apparent_wind_vector[1])
    yaw = math.degrees(from_bearing - heading)
    yaw_angle = (yaw + 180.0) % 360.0 - 180.0  # wrap to [-180, 180)

    return apparent_wind_speed, yaw_angle