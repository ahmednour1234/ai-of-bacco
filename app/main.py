"""
app/main.py
------------
FastAPI application factory with lifespan, middleware, and global exception handlers.
Equivalent to Laravel's bootstrap/app.php + Kernel.php.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.response import error_response

settings = get_settings()


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown logic equivalent to Laravel's service providers."""
    # Startup — nothing to initialize for the DB (handled per-request via get_db)
    yield
    # Shutdown — dispose of any open connections if needed


# ── Exception handlers ─────────────────────────────────────────────────────────

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return error_response(
        message=exc.message,
        errors=exc.errors,
        status_code=exc.status_code,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error.",
            "data": None,
            "meta": None,
        },
    )


# ── Factory ────────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description="AI-Powered Product Intelligence Platform API",
        lifespan=lifespan,
        docs_url="/docs" if settings.APP_DEBUG else None,
        redoc_url="/redoc" if settings.APP_DEBUG else None,
    )

    # ── CORS ────────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ───────────────────────────────────────────────────────
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ── Routers ──────────────────────────────────────────────────────────────────
    from app.api.v1.router import v1_router
    app.include_router(v1_router, prefix="/api")

    # ── Static file serving for local storage ────────────────────────────────────
    if settings.STORAGE_DRIVER == "local":
        from pathlib import Path
        from fastapi.staticfiles import StaticFiles
        storage_path = Path(settings.STORAGE_LOCAL_PATH)
        storage_path.mkdir(parents=True, exist_ok=True)
        app.mount("/storage", StaticFiles(directory=str(storage_path)), name="storage")

    return app


# ── ASGI entry-point ───────────────────────────────────────────────────────────
app = create_app()
