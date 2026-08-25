"""Application configuration.

All environment-driven configuration is centralized here as a single,
type-validated Settings object. No other module should call
``os.environ`` or ``os.getenv`` directly — everything goes through
``settings`` so there is exactly one place that knows how configuration
is sourced and validated.

Spring Boot equivalent: this plays the role of ``application.yml`` plus
an ``@ConfigurationProperties`` bean.
"""
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings, loaded from environment
    variables (and a local .env file in development).

    Every field has an explicit type so misconfiguration (a missing
    DATABASE_URL, a malformed boolean, etc.) fails fast at startup
    instead of surfacing as an obscure runtime error later.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Application ---
    APP_NAME: str = "Launch PO System"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # --- Security ---
    SECRET_KEY: str

    # --- Database ---
    DATABASE_URL: str

    # --- CORS ---
    # Stored as a raw comma-separated string in the environment, exposed
    # to the rest of the app as a parsed list via ALLOWED_ORIGINS_LIST.
    ALLOWED_ORIGINS: str = ""

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        normalized = value.upper()
        if normalized not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}, got {value!r}")
        return normalized

    @property
    def ALLOWED_ORIGINS_LIST(self) -> List[str]:
        """Parsed, whitespace-trimmed list of allowed CORS origins."""
        if not self.ALLOWED_ORIGINS:
            return []
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings singleton.

    Wrapped in ``lru_cache`` so the .env file and environment are only
    read once per process, and so FastAPI's dependency injection
    (``Depends(get_settings)``) reuses the same instance everywhere —
    equivalent to a Spring ``@Bean`` scoped as a singleton.
    """
    return Settings()


settings = get_settings()
print("DATABASE URL USED:", settings.DATABASE_URL)