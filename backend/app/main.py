"""FastAPI application entry point with CORS and router configuration."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.jobs_pages import router as jobs_pages_router
from app.api.v1.jobs_stream import router as jobs_stream_router
from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup
    yield
    # Shutdown


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    api_prefix = settings.API_V1_PREFIX
    app.include_router(health_router, prefix=api_prefix, tags=["health"])
    app.include_router(jobs_router, prefix=api_prefix, tags=["jobs"])
    app.include_router(jobs_pages_router, prefix=api_prefix, tags=["jobs"])
    app.include_router(jobs_stream_router, prefix=api_prefix, tags=["jobs"])

    return app


app = create_app()
