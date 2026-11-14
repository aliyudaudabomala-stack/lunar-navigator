"""FastAPI application entry point.

Run from the ``backend`` directory:

    .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload

The built React frontend (``frontend/dist``) is served from the same origin when
present, so a single process can host the whole application.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import analysis, astronomy, compare, health, horizons, reports, sites, terrain
from .core.config import PROJECT_DIR, get_settings
from .services.terrain_service import dem_info, get_terrain

logger = logging.getLogger("lunar_navigator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        terrain = get_terrain()
        meta = dem_info()
        logger.info(
            "Terrain ready: %s (%s), source=%s",
            meta["product_id"],
            "LOLA DEM" if meta["available"] else "illustrative fallback",
            type(terrain).__name__,
        )
    except Exception:  # pragma: no cover - startup must not hard-fail
        logger.exception("Terrain initialisation failed; requests will use fallbacks")
    yield


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Lunar south-pole landing-site navigator. Combines NASA LOLA topography with "
        "analytical Sun/Moon/Earth ephemerides to assess illumination, direct-to-Earth "
        "geometry, terrain suitability and mission timing. Candidate sites are "
        "approximate exploration regions, not certified landing ellipses."
    ),
    lifespan=lifespan,
    contact={"name": "Lunar Navigator — NASA Space Apps Challenge 2026"},
    license_info={"name": "MIT"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1200)


@app.middleware("http")
async def timing_header(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    response.headers["X-Process-Time-ms"] = f"{elapsed_ms:.1f}"
    return response


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc), "code": "value_error"})


API = "/api/v1"
app.include_router(health.router, prefix=API)
app.include_router(sites.router, prefix=API)
app.include_router(terrain.router, prefix=API)
app.include_router(astronomy.router, prefix=API)
app.include_router(analysis.router, prefix=API)
app.include_router(compare.router, prefix=API)
app.include_router(reports.router, prefix=API)
app.include_router(horizons.router, prefix=API)

# Serve the production build when it exists. API routes above take precedence.
_DIST = PROJECT_DIR / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
else:  # pragma: no cover - development path
    @app.get("/", include_in_schema=False)
    def dev_root() -> dict:
        return {
            "message": "Lunar Navigator API is running. Build the frontend or use the Vite dev server.",
            "api": API,
            "docs": "/docs",
        }
