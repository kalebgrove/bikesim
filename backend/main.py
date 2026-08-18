from fastapi import FastAPI
from engine.route import Route as route_module
from engine.rider import Rider as rider_module
from engine.physics import simulate

app = FastAPI()

@app.get('/')
async def root():
    return {"message": "root location"}

@app.get('/simulate')
async def simulate_route():
    # Create a sample route and rider for simulation
    route = route_module.get_route_from_gpx("./data/encinitas.gpx")
    rider = rider_module(rider_mass=70, bike_mass=10, ftp=250, f_max=1000, cda=0.3, crr=0.005, inertia=1.0, wheel_radius=0.35, metabolic_efficiency=0.22)
    wind_velocity_vector = (0.0, 0.0)  # No wind for this example
    p_target = 250.0  # Target power in watts
    dt = 1.0  # Time step in seconds

    results, kcal_burned = simulate(rider, route, wind_velocity_vector, p_target, dt)

    return {"results": results, "kcal_burned": kcal_burned}

@app.post('/rider')
async def create_rider(rider_mass, bike_mass, ftp, f_max, cda, crr, inertia, wheel_radius, metabolic_efficiency):
    # Rider should be stored in a database of sorts.
    return {"message": "Rider created successfully", "rider": {
        "rider_mass": rider_mass,
        "bike_mass": bike_mass,
        "ftp": ftp,
        "f_max": f_max,
        "cda": cda,
        "crr": crr,
        "inertia": inertia,
        "wheel_radius": wheel_radius,
        "metabolic_efficiency": metabolic_efficiency
    }}

@app.post('/route')
async def upload_route(gpx_file: str):
    # Route should be stored in a database of sorts.
    route = route_module.get_route_from_gpx(gpx_file)
    return {"message": "Route uploaded successfully", "route": {
        "total_distance": route.total_distance(),
        "points": route.points
    }}
