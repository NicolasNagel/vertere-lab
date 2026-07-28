"""Application factory.

Run locally from ``backend/``:

    uv run uvicorn --factory app.main:create_app --reload

The factory pattern keeps import time free of side effects (no settings or
engine required just to import the module), which tests rely on.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.api.error_handlers import register_error_handlers
from app.api.middleware import RequestContextMiddleware
from app.api.routers import health
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.modules.address_lookup.api.routers import router as address_lookup_router
from app.modules.attendances.api.routers import router as attendances_router
from app.modules.billing.api.routers import router as billing_router
from app.modules.catalog.api.routers import exams_router
from app.modules.catalog.api.routers import router as catalog_router
from app.modules.clinics.api.routers import router as clinics_router
from app.modules.identity.api.routers import router as identity_router
from app.modules.imports.api.routers import router as imports_router
from app.modules.patients.api.routers import patients_router, species_router
from app.modules.veterinarians.api.routers import router as veterinarians_router
from app.shared.infrastructure.database import build_engine, build_session_factory

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # create_engine does not connect eagerly; the pool fills on first use.
        engine = build_engine(app_settings.database_url.get_secret_value())
        app.state.engine = engine
        app.state.session_factory = build_session_factory(engine)
        yield
        engine.dispose()

    app = FastAPI(
        title="Vertere Lab API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)

    api_router = APIRouter(prefix=API_PREFIX)
    api_router.include_router(health.router)
    api_router.include_router(identity_router)
    api_router.include_router(clinics_router)
    api_router.include_router(catalog_router)
    api_router.include_router(exams_router)
    api_router.include_router(veterinarians_router)
    api_router.include_router(patients_router)
    api_router.include_router(species_router)
    api_router.include_router(address_lookup_router)
    api_router.include_router(attendances_router)
    api_router.include_router(billing_router)
    api_router.include_router(imports_router)
    app.include_router(api_router)
    return app
