"""Global exception handlers.

Registers a small number of handlers on the FastAPI app so error
response shape is consistent everywhere: every error body looks like
``{"error_code": ..., "message": ..., "details": ...}``, regardless of
which layer raised it.
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.exceptions.base import AppException

logger = logging.getLogger(__name__)


def _error_body(error_code: str, message: str, details=None) -> dict:
    return {"error_code": error_code, "message": message, "details": details}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to the given app instance."""

    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(
            "handled_exception path=%s error_code=%s message=%s",
            request.url.path,
            exc.error_code,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.error_code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # FastAPI/Pydantic request-schema validation, distinct from our
        # own ValidationException (business-rule validation).
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                "REQUEST_VALIDATION_ERROR",
                "The request payload failed validation.",
                exc.errors(),
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        # Last-resort safety net: never let an unexpected exception leak
        # a stack trace or internal details to the client.
        logger.exception("unhandled_exception path=%s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                "INTERNAL_ERROR", "An unexpected error occurred.", None
            ),
        )
