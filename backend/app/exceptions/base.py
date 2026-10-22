"""Custom application exception hierarchy.

Services and repositories raise these instead of returning error codes
or raising raw ``Exception``. Routes never catch these directly — a
single set of global handlers (see ``app/exceptions/handlers.py``)
translates them into HTTP responses in one place, so every endpoint
gets consistent error formatting for free.

Spring Boot equivalent: a hierarchy of custom ``RuntimeException``
subclasses caught by an ``@ControllerAdvice``.
"""
from typing import Any, Optional


class AppException(Exception):
    """Base class for all application-raised exceptions.

    Carries an HTTP status code and a machine-readable error code
    alongside the human-readable message, so API clients can branch on
    ``error_code`` without parsing free text.
    """

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, details: Optional[Any] = None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)


class NotFoundException(AppException):
    """Raised when a requested resource does not exist."""

    status_code = 404
    error_code = "NOT_FOUND"


class ValidationException(AppException):
    """Raised for business-rule validation failures.

    Distinct from FastAPI/Pydantic's own request-schema validation
    (which is handled separately) — this is for validation that can
    only happen after looking at business data, e.g. a status
    transition rule.
    """

    status_code = 422
    error_code = "VALIDATION_ERROR"


class ConflictException(AppException):
    """Raised when an action conflicts with the current state of a
    resource (e.g. duplicate record, optimistic-lock version mismatch).
    """

    status_code = 409
    error_code = "CONFLICT"


class UnauthorizedException(AppException):
    """Raised when a user is not permitted to perform an action."""

    status_code = 401
    error_code = "UNAUTHORIZED"


class ForbiddenException(AppException):
    """Raised when an authenticated user is not allowed to perform an action."""

    status_code = 403
    error_code = "FORBIDDEN"
