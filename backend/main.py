"""CityBCPAgent — FastAPI Backend"""
import sys
from pathlib import Path

# Add parent dir so we can import existing utils/models/parsers/config
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

app = FastAPI(title="CityBCPAgent API", version="2.0")

_default_origins = "http://localhost:3000,http://localhost:5173,http://localhost:8000"
cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers
from backend.routers import auth, config, data, operations, ai, settings, charts, upload, insights, export

app.include_router(auth.router, prefix="/api", tags=["Auth"])
app.include_router(config.router, prefix="/api", tags=["Config"])
app.include_router(data.router, prefix="/api", tags=["Data"])
app.include_router(operations.router, prefix="/api", tags=["Operations"])
app.include_router(ai.router, prefix="/api", tags=["AI"])
app.include_router(settings.router, prefix="/api", tags=["Settings"])
app.include_router(charts.router, prefix="/api", tags=["Charts"])
app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(insights.router, prefix="/api", tags=["Insights"])
app.include_router(export.router, prefix="/api", tags=["Export"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve SvelteKit static build (must be AFTER all /api routes)
from starlette.responses import FileResponse

_fe_build = os.path.join(os.path.dirname(__file__), "..", "frontend", "build")
if os.path.isdir(_fe_build):

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(_fe_build, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(_fe_build, "index.html"))
