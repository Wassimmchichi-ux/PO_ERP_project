# Launch PO System — Backend

Backend foundation for the Purchase Order / Material Planning / Stock /
Delivery / Finance system. Built with FastAPI, SQLAlchemy 2.0, and
Alembic, using a layered architecture designed to port cleanly to
Spring Boot later:

```
API (routes)  →  Services  →  Repositories  →  SQLAlchemy Models  →  PostgreSQL
```

- Routes only receive/validate requests and call services. No business logic.
- Services own business logic and orchestrate repositories.
- Repositories are the only layer that talks to the database.

## Status

This is the **M0 milestone**: project skeleton only. No ERP entities
(Purchase Orders, Projects, Materials, etc.) are implemented yet —
those arrive in later milestones per the agreed roadmap.

## Project layout

```
backend/
├── app/
│   ├── api/            # FastAPI routers (controllers)
│   ├── core/            # Settings, logging — cross-cutting config
│   ├── db/               # Engine, session factory, declarative Base + mixins
│   ├── models/           # SQLAlchemy ORM models (empty until M1+)
│   ├── repositories/     # DB access layer (empty until M1+)
│   ├── services/         # Business logic (empty until M1+)
│   ├── schemas/          # Pydantic request/response DTOs (empty until M1+)
│   ├── exceptions/        # Custom exceptions + global handlers
│   ├── dependencies/      # FastAPI dependency providers (e.g. get_db)
│   ├── middleware/        # Request logging, etc.
│   └── main.py            # App factory / entry point
├── migrations/            # Alembic migrations
├── tests/
├── requirements.txt
├── .env.example
└── alembic.ini
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env with your local DATABASE_URL and a real SECRET_KEY
```

Requires a running PostgreSQL instance matching `DATABASE_URL`.

## Running

```bash
uvicorn app.main:app --reload
```

Then check:

```bash
curl http://localhost:8000/health
# {"status": "healthy"}
```

## Testing

```bash
pytest
```

## Migrations

No tables exist yet (no ERP models). Once the first models land:

```bash
alembic revision --autogenerate -m "add <entity>"
alembic upgrade head
```

## Configuration

All environment variables are documented in `.env.example`. Settings
are loaded and validated once at startup via `app/core/config.py` —
the app will refuse to start if a required variable is missing or
malformed, rather than failing later at an unpredictable point.
