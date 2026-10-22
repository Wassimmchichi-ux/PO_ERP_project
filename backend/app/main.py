"""Application entry point.

Assembles the FastAPI app from all the pieces configured elsewhere:
settings, logging, CORS, request logging, global exception handlers,
and routers. No business logic and no route definitions live here —
this file only wires things together.

Run locally with:
    uvicorn app.main:app --reload
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.admin import router as admin_router
from app.api.bom import router as bom_router
from app.api.customer_delivery import router as customer_delivery_router
from app.api.handover import router as handover_router
from app.api.parsed_purchase_order import router as parsed_purchase_order_router
from app.api.projects import router as projects_router
from app.api.stock import router as stock_router
from app.api.simulation import router as simulation_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.exceptions.handlers import register_exception_handlers
from app.middleware.request_logging import RequestLoggingMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks, using FastAPI's current lifespan API
    (the ``@app.on_event`` decorators are deprecated).
    """
    logger.info(
        "app_startup app_name=%s environment=%s debug=%s",
        settings.APP_NAME,
        settings.ENVIRONMENT,
        settings.DEBUG,
    )
    yield
    logger.info("app_shutdown")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance.

    Using a factory function (rather than a bare module-level ``app =
    FastAPI()``) keeps app construction testable — tests can call
    ``create_app()`` fresh with overridden dependencies instead of
    sharing global state.
    """
    configure_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS_LIST,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    register_exception_handlers(app)

    # Register API routers
    app.include_router(health_router)
    app.include_router(admin_router)
    app.include_router(bom_router)
    app.include_router(projects_router)
    app.include_router(parsed_purchase_order_router)
    from app.api.cutting_reports import router as cutting_reports_router
    app.include_router(cutting_reports_router)
    app.include_router(stock_router)
    app.include_router(simulation_router)
    app.include_router(handover_router)
    app.include_router(customer_delivery_router)

    return app


app = create_app()
