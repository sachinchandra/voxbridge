"""VoxBridge Platform API - Main FastAPI application.

This is the SaaS backend that powers the VoxBridge dashboard.
It handles customer auth, API key management, usage tracking, and billing.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.api import agents, auth, billing, calls, keys, phone_numbers, usage, webhooks

# ──────────────────────────────────────────────────────────────────
# Application factory
# ──────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="VoxBridge Platform API",
        description="AI-First Contact Center Platform — Replace Genesys, not integrate with it",
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(keys.router, prefix="/api/v1")
    app.include_router(usage.router, prefix="/api/v1")
    app.include_router(billing.router, prefix="/api/v1")
    app.include_router(agents.router, prefix="/api/v1")
    app.include_router(calls.router, prefix="/api/v1")
    app.include_router(phone_numbers.router, prefix="/api/v1")
    app.include_router(webhooks.router, prefix="/api/v1")

    # Health check
    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "voxbridge-platform"}

    @app.get("/")
    async def root():
        return {
            "name": "VoxBridge AI Contact Center API",
            "version": "0.2.0",
            "docs": "/docs",
        }

    logger.info("VoxBridge Platform API initialized")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
