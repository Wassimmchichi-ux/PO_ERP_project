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

The [setup guide](../docs/TECHNICAL_DOCUMENTATION.md#2-local-deployment) documents the local runtime. Normal startup does not reset data. The current head is `e9a1c4f6b802`. For disposable development data, `python -m app.db.bootstrap --seed-demo-workflows` idempotently adds a supplier transit order and a manual warehouse reception without resetting the database.

The current PDFs preserve five-decimal prices, XLSX BOM uploads retain source units and commit atomically, and cutting XLSX reports preserve original bytes before explicit consumption posting. Source files live under `../ressources/business-test/`. Tests read those actual files.

## Structure and checks

Routes are in `app/api`, business workflows in `app/services`, persistence in `app/repositories`, mappings in `app/models`, contracts in `app/schemas`, and prototype authorization in `app/policies`. Some services query the ORM directly. BOM uploads defer repository commit to the complete upload transaction.

```bash
PYTHONDONTWRITEBYTECODE=1 DEBUG=false .venv/bin/python -m pytest -q -p no:cacheprovider
```

On 23 October 2026, the suite contains **99 tests**: 97 non-HTTP tests pass in the restricted runner, and its worker-thread limitation prevents the two in-process HTTP tests from completing. Live Docker checks confirm supplier orders and transit return matching source and quantity fields; they also cover stock summary, reception history, and the baseline ledger. The PostgreSQL upgrade, frontend type checking/lint/build, source-document checks, and focused eight-test supplier/warehouse workflow suite also pass. [Verification details](../docs/TECHNICAL_DOCUMENTATION.md#10-verification) state the scope and limits.

Authentication remains a prototype header mechanism. Simulations reserve physical stock and launch retries are idempotent, but material issue does not create the complete downstream launch records. This and the unmatched source identifiers are recorded in the issues register.
