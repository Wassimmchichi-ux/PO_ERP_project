> Historical documentation. This describes an earlier implementation and may contain superseded behavior, paths, or test results. For the working-tree review dated 21 October 2026, use the [business documentation](../../docs/BUSINESS_DOCUMENTATION.md) and [technical documentation](../../docs/TECHNICAL_DOCUMENTATION.md).

# Milestone M0 — Backend Foundation

## Summary

M0 delivers the project skeleton for the Launch PO / Material Planning / Stock /
Delivery / Finance backend: a working, tested, runnable FastAPI application with
no ERP business entities yet. Every later milestone (User Management, Purchase
Orders, BOM, Stock, Simulation, Delivery, Finance, Audit) builds on top of this
without needing to touch it structurally.

Stack: **Python 3.13+, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, Pydantic v2,
Uvicorn, pytest.**

Architecture: strict layering, designed to port cleanly to Spring Boot later.

```
API (routes) → Services → Repositories → SQLAlchemy Models → PostgreSQL
```

- Routes only receive/validate requests and call services — no business logic.
- Services own business logic (empty until M1+).
- Repositories are the only layer allowed to touch the database (empty until M1+).

---

## Project structure

```
backend/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   └── health.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── logging.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── session.py
│   ├── dependencies/
│   │   ├── __init__.py
│   │   └── db.py
│   ├── exceptions/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── handlers.py
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── request_logging.py
│   ├── models/          (empty — no ERP entities yet)
│   ├── repositories/    (empty — no ERP entities yet)
│   ├── services/        (empty — no ERP entities yet)
│   ├── schemas/         (empty — no ERP entities yet)
│   ├── utils/           (empty)
│   ├── __init__.py
│   └── main.py
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/        (empty — no business tables yet)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_health.py
├── .env
├── .env.example
├── .gitignore
├── alembic.ini
├── requirements.txt
└── README.md
```

---

## File-by-file description

### `requirements.txt`
Pinned, minimal dependency list: FastAPI, Uvicorn, SQLAlchemy, Alembic,
`psycopg2-binary`, Pydantic + `pydantic-settings`, `python-dotenv`, and the
pytest/httpx testing stack. No auth libraries yet — those arrive with M1 (User
Management) so the dependency list always reflects what's actually implemented.

### `.env.example` / `.env`
Documents every required environment variable: `APP_NAME`, `ENVIRONMENT`,
`DEBUG`, `LOG_LEVEL`, `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_ORIGINS`.
`.env.example` is safe to commit; `.env` is git-ignored and holds real
(dev-only) values, including a randomly generated `SECRET_KEY`.

### `.gitignore`
Standard Python/FastAPI ignores: `.env`, `__pycache__/`, virtualenvs, test
caches, IDE folders.

### `app/core/config.py`
A single Pydantic `Settings` class (`BaseSettings`) as the one source of truth
for all configuration — no other module reads `os.environ` directly.

- `LOG_LEVEL` is validated against a fixed set at startup (a typo fails fast
  instead of silently misbehaving later).
- `ALLOWED_ORIGINS` is stored as a raw comma-separated string and exposed as a
  parsed `ALLOWED_ORIGINS_LIST` property.
- `get_settings()` is `lru_cache`d and also re-exported as a module-level
  `settings`, so it can be imported directly (`from app.core.config import
  settings`) or injected via FastAPI's `Depends(get_settings)`.
- Spring Boot equivalent: `application.yml` + an `@ConfigurationProperties`
  bean.

### `app/core/logging.py`
`configure_logging()`, called once at startup, configures the root logger with
a custom `StructuredFormatter` that renders `key=value` structured lines
(readable in a terminal, still greppable/parseable) rather than raw JSON.
Third-party loggers (`sqlalchemy.engine`, `uvicorn.access`) are quieted unless
`LOG_LEVEL=DEBUG`.

### `app/db/base.py`
SQLAlchemy 2.0 declarative `Base`, plus three **opt-in** mixins:

- `UUIDPrimaryKeyMixin` — app-generated UUID primary keys (`uuid.uuid4`),
  avoiding sequential-ID leakage and allowing IDs to exist before a row is
  persisted.
- `TimestampMixin` — `created_at` / `updated_at`, stamped by the database via
  `server_default=func.now()` / `onupdate=func.now()`, so the DB (not
  app-server clocks) is the source of truth.
- `SoftDeleteMixin` — nullable `deleted_at` + `is_deleted` property. Mixed in
  explicitly per model, not applied globally — some SRS entities (audit
  records) must never be deletable at all, soft or otherwise.

No ERP entities defined here — purely shared foundation.

### `app/db/session.py`
The SQLAlchemy `engine` (created once, `pool_pre_ping=True` to avoid stale
connection errors) and the `SessionLocal` sessionmaker
(`expire_on_commit=False` so services can read attributes right after commit
without a surprise implicit re-query). Also exposes `get_session()` for
non-web use (scripts, background tasks).

### `app/dependencies/db.py`
The FastAPI dependency `get_db()` — the only place routes/services should get a
database session from in the web context. Yields one session per request,
rolls back on exception, always closes in `finally`. Spring Boot equivalent:
the request-scoped `EntityManager` Spring Data JPA manages automatically.

### `app/exceptions/base.py`
Custom exception hierarchy: `AppException` (base, carries `status_code` +
`error_code` + `message` + optional `details`) with four subclasses —
`NotFoundException` (404), `ValidationException` (422), `ConflictException`
(409), `UnauthorizedException` (401). Services/repositories raise these
instead of raw exceptions or ad hoc error returns.

### `app/exceptions/handlers.py`
`register_exception_handlers(app)` attaches three global handlers:

1. `AppException` → consistent `{error_code, message, details}` JSON + a
   warning-level log line.
2. `RequestValidationError` (FastAPI/Pydantic's own request-schema validation,
   kept distinct from our business-rule `ValidationException`) → 422 with
   field-level errors.
3. Catch-all `Exception` → 500, full stack trace logged server-side, generic
   message returned to the client (never leaks internals).

### `app/middleware/request_logging.py`
`RequestLoggingMiddleware` generates a UUID per request, times the request,
logs `request_id`, `method`, `path`, `status`, `duration_ms`, and echoes the
ID back as an `X-Request-ID` response header — so any request can be traced
through the logs before any business logic even runs.

### `app/api/health.py`
`GET /health` → `{"status": "healthy"}`. Deliberately has no DB dependency —
it answers "is the process up," which is what liveness checks need. A
separate `/health/ready` DB-connectivity check can be added once there are
real tables to query.

### `app/main.py`
The application factory (`create_app()`), used instead of a bare module-level
`app = FastAPI()` so tests can construct fresh, independent app instances.
Wires together, in order: `configure_logging()` → `FastAPI(...)` with a
`lifespan` context manager (startup/shutdown logging, using the current
non-deprecated lifespan API rather than `@app.on_event`) → CORS middleware
(origins from settings) → `RequestLoggingMiddleware` → global exception
handlers → the health router. `app = create_app()` at module level is the
Uvicorn entry point (`uvicorn app.main:app`).

### `alembic.ini`
Alembic configuration with `sqlalchemy.url` left blank on purpose — the real
URL is injected at runtime from `app.core.config.settings` in `migrations/env.py`,
so the connection string exists in exactly one place, never duplicated.

### `migrations/env.py`
Sets `sqlalchemy.url` from `settings.DATABASE_URL` and points
`target_metadata` at `Base.metadata`. Includes a marked spot for importing
model modules once they exist, so `alembic revision --autogenerate` can see
them. Supports both offline (SQL-only) and online migration modes.

### `migrations/script.py.mako`
Standard Alembic revision template (`upgrade()` / `downgrade()`), unmodified
from Alembic's default beyond formatting.

### `tests/conftest.py`
A `client` fixture returning a `TestClient` built from `create_app()` (not the
shared `app` instance), so future tests can override dependencies (e.g. inject
a fake DB session) independently per test.

### `tests/test_health.py`
Smoke test asserting `GET /health` returns `200` and
`{"status": "healthy"}`.

### `README.md`
Project overview, layout, setup instructions, run/test commands, and the
Alembic migration workflow for future milestones.

---

## Key design decisions

| Decision | Rationale |
|---|---|
| **Sync SQLAlchemy** (`psycopg2-binary`), not async | Spring Data JPA/Hibernate sessions are blocking — sync SQLAlchemy sessions translate far more directly into their Spring equivalents. FastAPI runs sync routes in a threadpool automatically, so this doesn't cost meaningful throughput at prototype scale; swapping to async later is isolated to `db/session.py`. |
| **App factory (`create_app()`)**, not a bare `app = FastAPI()` | Keeps construction testable — each test can build an independent instance instead of sharing global state. |
| **`lifespan` context manager**, not `@app.on_event` | `on_event` is deprecated in current FastAPI; caught and fixed during verification (see below). |
| **Mixins are opt-in per model**, not applied to a global base | Some SRS entities (audit/traceability records) must be genuinely immutable/non-deletable — soft-delete must be a conscious choice per model, not automatic. |
| **`AppException` hierarchy + centralized handlers** | Every error response has the same shape regardless of which layer raised it — no per-route try/except boilerplate. |
| **`DATABASE_URL` lives only in settings**, injected into Alembic at runtime | One source of truth for the connection string; `alembic.ini` never duplicates it. |
| **Minimal, honest `requirements.txt`** | Only what M0 actually uses — no speculative auth/JWT libraries added until M1 needs them. |

---

## Verification performed

Before delivery, the skeleton was actually run, not just written:

- `pytest tests/` → **1 passed** (health check).
- Full app boot via `TestClient(app)` → `GET /health` returned `200
  {"status": "healthy"}` with a valid `X-Request-ID` response header, and
  startup/shutdown log lines fired correctly through the structured logger.
- `alembic current` → config loaded and correctly resolved `DATABASE_URL` from
  settings; it failed only at the final connection step because no Postgres
  instance exists in this environment (`Connection refused` on
  `localhost:5432`) — the expected failure mode, confirming the wiring itself
  is correct.
- A deprecation warning surfaced during the first test run
  (`@app.on_event` is deprecated) and was fixed by switching to the
  `lifespan` context manager before final delivery.

---

## What's deliberately NOT in M0

- No ERP entities (`Project`, `PurchaseOrder`, `Material`, etc.) — those start
  at M1/M2 per the roadmap.
- No authentication/authorization implementation — `SECRET_KEY` exists in
  config as a placeholder for M1, but no JWT/session logic exists yet.
- No business logic anywhere — `services/`, `repositories/`, `schemas/` are
  empty packages, present only so the layering is established from the start.
- No Alembic migrations — the migration *infrastructure* exists and is
  verified working, but there is nothing to migrate yet (no models).

## Next milestone

**M1 — User Management & Access Control (SRS module M00)**: `AppUser` model,
role enum, `ProjectAssignment`, authentication, and the first real Alembic
migration.
