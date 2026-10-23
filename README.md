# Adient ERP Prototype

Industrial ERP prototype developed by Wassim Mchichi for purchase-order intake, bills of materials, material simulation, stock, warehouse handover, cutting consumption, and customer-delivery follow-up.

## Local app

The Docker deployment checked on 23 October 2026 is available at:

- **Application:** http://localhost:5173
- **Backend/API reference:** http://localhost:8080/docs
- **Backend health:** http://localhost:8080/health

Start or rebuild it from this directory:

```bash
docker compose up -d --build
```

Startup initializes an empty PostgreSQL schema or upgrades an existing versioned database. It never resets records automatically. Add repeatable supplier/transit/reception examples with `docker compose exec backend python -m app.db.bootstrap --seed-demo-workflows`. For native development and the explicit disposable-data reset/seed commands, see the [setup guide](docs/TECHNICAL_DOCUMENTATION.md#2-local-deployment).

## Documentation

- [Business documentation](docs/BUSINESS_DOCUMENTATION.md): workflows for each user type, business rules, implementation boundaries, and acceptance scenarios.
- [Technical documentation](docs/TECHNICAL_DOCUMENTATION.md): architecture, stock/database model, simulation algorithms, document formats, API integration, migrations, and verification.
- [Technical and business issues only](docs/ISSUES_REGISTER.md): remaining defects, business decisions, consequences, priorities, and evidence.

The current business-test documents are supported: three Adient PO PDFs, the two-FGPN MBOM workbook, and the cutting-report workbook. PO/BOM/cutting identifiers do not match each other, so no associations were invented. Cutting usage needs explicit launch/unit confirmation before posting.

The frontend and backend now share one **Order + Manual Entry** planner across multiple POs/FGPNs. Allocation uses production remainder, warehouse, then optional transit due by the target date. Physical units are selected globally per material, saved simulations reserve them, and launch retries are idempotent. Administrators maintain the supplier master; launch engineers/managers select a supplier and plan quantities/ETAs; the system generates stock-unit IDs; warehouse personnel record received quantities; and team leaders confirm arrivals. The frontend uses Adient branding.

## Verification and boundaries

The backend suite contains **99 tests**. In this restricted runner, 97 non-HTTP tests pass; the two in-process HTTP transport tests hang because the runner prevents worker-thread dispatch. Live Docker checks confirm the supplier order and transit endpoints expose the same order, project, generated reference, planned quantity, actual quantity, and workflow state. Stock summary, reception, and history use the same database records. Frontend TypeScript checking, linting, and the production build pass. The local PostgreSQL database is at migration `e9a1c4f6b802`. Several older screens still use demonstration data, and authentication plus the downstream launch/handover chain remain incomplete. See the issues register before relying on the prototype operationally.

## Repository

- `backend/`: FastAPI services, models, active migrations, and tests.
- `frontend/`: React/TanStack application.
- `docs/`: current documentation and issues register.
- `ressources/business-test/`: current source PDFs and XLSX workbooks.
- `ressources/database/`: historical SQL artifact; not the fresh-install path.
- `archive/`: historical documentation, reports, and older frontend copy.
# PO_ERP_project
