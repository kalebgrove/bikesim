import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.riders import router as riders_router
from routes.routes import router as routes_router
from routes.simulations import router as simulations_router

app = FastAPI()

DEFAULT_ORIGINS = "http://localhost:5173,http://localhost:8443,http://127.0.0.1:5173,http://127.0.0.1:8443"
origins = [origin.strip() for origin in os.getenv("FRONTEND_ORIGINS", DEFAULT_ORIGINS).split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(riders_router)
app.include_router(routes_router)
app.include_router(simulations_router)

@app.get('/')
async def root():
    return {"message": "root location"}

@app.get('/health')
async def health():
    return {"status": "ok"}