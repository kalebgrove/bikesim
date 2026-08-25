import base64
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
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

SITE_PASSWORD = os.getenv("SITE_PASSWORD", "")

LOGIN_HTML = """<!DOCTYPE html>
<html><head><title>BikeSim</title>
<style>
  body{display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;
       background:#0f172a;font-family:system-ui,sans-serif;color:#e2e8f0}
  form{background:#1e293b;padding:2rem;border-radius:12px;box-shadow:0 4px 24px #0005}
  h2{margin:0 0 1rem;text-align:center}
  input{width:100%;padding:.6rem;margin-bottom:1rem;border:1px solid #334155;border-radius:6px;
        background:#0f172a;color:#e2e8f0;font-size:1rem;box-sizing:border-box}
  button{width:100%;padding:.6rem;background:#3b82f6;color:#fff;border:none;border-radius:6px;
         font-size:1rem;cursor:pointer}
  button:hover{background:#2563eb}
</style></head>
<body>
<form method="POST">
  <h2>BikeSim</h2>
  <input type="password" name="password" placeholder="Password" autofocus>
  <button type="submit">Enter</button>
</form></body></html>"""


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    if not SITE_PASSWORD:
        return await call_next(request)

    if request.url.path.startswith("/health"):
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth[6:]).decode()
            _, password = decoded.split(":", 1)
            if password == SITE_PASSWORD:
                return await call_next(request)
        except Exception:
            pass

    if request.method == "POST" and request.url.path == "/":
        form = await request.form()
        if form.get("password") == SITE_PASSWORD:
            from starlette.responses import RedirectResponse
            response = RedirectResponse("/", status_code=302)
            response.set_cookie("auth", SITE_PASSWORD, httponly=True, max_age=86400 * 30, samesite="lax")
            return response

    if request.cookies.get("auth") == SITE_PASSWORD:
        return await call_next(request)

    return HTMLResponse(LOGIN_HTML, status_code=401, headers={"WWW-Authenticate": 'Basic realm="BikeSim"'})

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