import math

def apparent_wind(bike_velocity_vector, wind_velocity_vector) -> tuple[float, float]:
    """
    Calculate the apparent wind speed and angle based on the bike's velocity and the wind's velocity.

    Parameters:
    bike_velocity_vector (tuple): A tuple containing the bike's velocity components (vx, vy).
    wind_velocity_vector (tuple): A tuple containing the wind's velocity components (wx, wy).

    Returns:
    tuple: A tuple containing the apparent wind speed and angle in degrees.
    """
    # Calculate the apparent wind vector
    apparent_wind_vector = (wind_velocity_vector[0] - bike_velocity_vector[0],
                            wind_velocity_vector[1] - bike_velocity_vector[1])

    # Calculate the magnitude of the apparent wind vector
    apparent_wind_speed = math.sqrt(apparent_wind_vector[0] ** 2 + apparent_wind_vector[1] ** 2)

    # Calculate the angle of the apparent wind vector in degrees
    yaw_angle = math.degrees(math.atan2(apparent_wind_vector[1], apparent_wind_vector[0]))

    return apparent_wind_speed, yaw_angle