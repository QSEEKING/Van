"""
CoPaw Code REST API

FastAPI-based REST API for CoPaw Code AI coding assistant.
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.config import get_settings

# Version info
__version__ = "0.1.0"
__author__ = "CoPaw Team"


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str
    timestamp: str


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    detail: str | None = None
    request_id: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    settings = get_settings()
    app.state.settings = settings
    print(f"CoPaw Code API v{__version__} starting...")
    yield
    # Shutdown
    print("CoPaw Code API shutting down...")


app = FastAPI(
    title="CoPaw Code API",
    description="AI-powered coding assistant REST API",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc) if str(exc) else None,
        },
    )


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns the current status and version of the API.
    """
    from datetime import datetime, timezone

    return HealthResponse(
        status="healthy",
        version=__version__,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/version", tags=["System"])
async def get_version() -> dict[str, str]:
    """
    Get API version information.
    """
    return {
        "version": __version__,
        "name": "CoPaw Code API",
        "author": __author__,
    }


@app.get("/config", tags=["System"])
async def get_current_config() -> dict[str, Any]:
    """
    Get current configuration (non-sensitive values only).
    """
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "debug": settings.debug,
        "log_level": str(settings.log_level),
        "llm_provider": str(settings.default_provider),
        "llm_model": settings.default_model,
    }


# Import and include routers
from api.rest.routes import agents_router, sessions_router, tools_router

app.include_router(agents_router, prefix="/agents", tags=["Agents"])
app.include_router(tools_router, prefix="/tools", tags=["Tools"])
app.include_router(sessions_router, prefix="/sessions", tags=["Sessions"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
