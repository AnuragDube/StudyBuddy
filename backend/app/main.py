"""FastAPI application entry point.

Run locally with::

    uvicorn app.main:app --reload --port 8000

Swagger UI is served at ``/docs`` and ReDoc at ``/redoc``.
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, plans, settings as settings_routes
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.init_db import run_migrations

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        "Starting %s", settings.app_name,
        extra={"version": settings.app_version, "environment": settings.environment},
    )
    if settings.auto_migrate:
        run_migrations(settings.database_url)
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Multi-Subject AI Study Planner with Shared Workload Management. "
            "An LLM extracts syllabus topics; a deterministic scheduler allocates "
            "study sessions within one shared daily capacity."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["x-request-id"] = request_id
        logger.info(
            "%s %s -> %s", request.method, request.url.path, response.status_code,
            extra={"request_id": request_id, "duration_ms": elapsed_ms},
        )
        return response

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(settings_routes.router, prefix=settings.api_prefix)
    app.include_router(plans.router, prefix=settings.api_prefix)
    return app


app = create_app()
