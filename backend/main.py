import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        file = FRONTEND_DIR / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(FRONTEND_DIR / "index.html")
else:
    @app.get('/')
    async def root():
        return {"message": "root location", "hint": "Frontend not built. Run 'cd frontend && npm run build'."}

@app.get('/health')
async def health():
    return {"status": "ok"}