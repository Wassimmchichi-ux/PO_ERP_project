"""Logging configuration.

Configures structured, consistent logging for the whole application.
Called once at startup from ``main.py``. Every other module just uses
``logging.getLogger(__name__)`` as normal — this module only owns *how*
those log records are formatted and where they go.
"""
import logging
import sys

from app.core.config import settings


class StructuredFormatter(logging.Formatter):
    """Renders log records as single-line, key=value structured text.

    Chosen over raw JSON for the prototype phase: it's still greppable
    and machine-parseable, but far more readable in a local terminal
    than JSON-per-line. Swapping to JSON later (e.g. for shipping to a
    log aggregator) is a one-formatter change, not a structural one.
    """

    def format(self, record: logging.LogRecord) -> str:
        base = (
            f"timestamp={self.formatTime(record, datefmt='%Y-%m-%dT%H:%M:%S%z')} "
            f"level={record.levelname} "
            f"logger={record.name} "
            f"message={record.getMessage()!r}"
        )
        if record.exc_info:
            base += f"\n{self.formatException(record.exc_info)}"
        return base


def configure_logging() -> None:
    """Configure the root logger for the application process.

    Idempotent-ish: safe to call once at startup. Re-running it would
    duplicate handlers, so callers should not call it more than once
    per process (main.py's startup event is the single call site).
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())

    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Quiet down noisy third-party loggers unless we're actively debugging.
    if settings.LOG_LEVEL != "DEBUG":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
