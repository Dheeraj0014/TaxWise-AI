"""FastAPI app factory (§9.1). Mounts /api/v1 routers + middleware."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers import (auth, dashboard, finances, optimizer, profile,
                                recommendations, tax)
from app.core.config import get_settings
from app.core.database import init_db

DISCLAIMER = (
    "AI Tax Optimizer is an informational tool, not tax or financial advice. "
    "Tax rules change with every Union Budget — verify against the current "
    "Finance Act and consult a qualified professional before filing."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=DISCLAIMER,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "environment": settings.environment}

    @app.get("/api/v1/disclaimer", tags=["meta"])
    def disclaimer() -> dict:
        return {"disclaimer": DISCLAIMER}

    api_prefix = "/api/v1"
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(profile.router, prefix=api_prefix)
    app.include_router(finances.router, prefix=api_prefix)
    app.include_router(tax.router, prefix=api_prefix)
    app.include_router(optimizer.router, prefix=api_prefix)
    app.include_router(recommendations.router, prefix=api_prefix)
    app.include_router(dashboard.router, prefix=api_prefix)

    return app


app = create_app()
