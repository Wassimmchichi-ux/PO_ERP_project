# Adient ERP Backend

FastAPI, SQLAlchemy, and PostgreSQL services for purchase orders, BOMs, material simulation, stock, cutting reports, projects, administration, handover, and customer delivery.

## Documentation

- [Business workflows](../docs/BUSINESS_DOCUMENTATION.md)
- [Technical implementation and document formats](../docs/TECHNICAL_DOCUMENTATION.md)
- [Remaining technical and business issues](../docs/ISSUES_REGISTER.md)

## Local development

Use Python 3.13 and install `requirements.txt` in a virtual environment. Configure `DATABASE_URL`, `SECRET_KEY`, and `ALLOWED_ORIGINS` using `.env.example`; preserve any existing local settings. Native database credentials must match the actual server. Compose's `db` hostname is for container networking.

From this directory:

```bash
DEBUG=false .venv/bin/python -m app.db.bootstrap
DEBUG=false .venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Native API reference: http://localhost:8000/docs. Docker exposes the API at http://localhost:8080/docs and the frontend at http://localhost:5173. `/health` is a liveness check, not a database readiness check.

## Database and source documents

`app/db/bootstrap.py` creates empty PostgreSQL schemas from the active ORM metadata and stamps the current Alembic head, or upgrades existing versioned schemas. `alembic.ini` selects `migrations/`. The separate `alembic/`, `app/models/domain.py`, and SQL dump are historical representations.

The [setup guide](../docs/TECHNICAL_DOCUMENTATION.md#23-database-initialization-and-document-test-data) documents explicit reset/seeding of disposable test data. Normal startup does neither. The current head is `e0f4a6b8c123`.

The current PDFs preserve five-decimal prices, XLSX BOM uploads retain source units and commit atomically, and cutting XLSX reports preserve original bytes before explicit consumption posting. Source files live under `../ressources/business-test/`. Tests read those actual files.

## Structure and checks

Routes are in `app/api`, business workflows in `app/services`, persistence in `app/repositories`, mappings in `app/models`, contracts in `app/schemas`, and prototype authorization in `app/policies`. Some services query the ORM directly. BOM uploads defer repository commit to the complete upload transaction.

```bash
PYTHONDONTWRITEBYTECODE=1 DEBUG=false .venv/bin/python -m pytest -q -p no:cacheprovider
```

On 22 October 2026: **91 passed**. PostgreSQL upgrade, fresh schema/reset, source-document seed, and local API checks also passed. [Verification details](../docs/TECHNICAL_DOCUMENTATION.md#9-verification-performed) state the scope and limits.

Authentication remains a prototype header mechanism. Simulation saving does not reserve stock, and material issue does not create the complete downstream launch records. These and the unmatched source identifiers are recorded in the issues register.
