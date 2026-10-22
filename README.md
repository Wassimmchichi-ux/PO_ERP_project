# Adient ERP Prototype

Industrial ERP prototype developed by Wassim Mchichi for purchase-order intake, bills of materials, material simulation, stock, warehouse handover, cutting consumption, and customer-delivery follow-up.

## Local app

The Docker deployment checked on 22 October 2026 is available at:

- **Application:** http://localhost:5173
- **Backend/API reference:** http://localhost:8080/docs
- **Backend health:** http://localhost:8080/health

Start or rebuild it from this directory:

```bash
docker compose up -d --build
```

Startup initializes an empty PostgreSQL schema or upgrades an existing versioned database. It never resets records automatically. For native development and the explicit disposable-data reset/seed command, see the [setup guide](docs/TECHNICAL_DOCUMENTATION.md#2-runtime-and-local-setup).

## Documentation

- [Business documentation](docs/BUSINESS_DOCUMENTATION.md): workflows for each user type, business rules, implementation boundaries, and acceptance scenarios.
- [Technical documentation](docs/TECHNICAL_DOCUMENTATION.md): architecture, stock/database model, simulation algorithms, document formats, API integration, migrations, and verification.
- [Technical and business issues only](docs/ISSUES_REGISTER.md): remaining defects, business decisions, consequences, priorities, and evidence.

The current business-test documents are supported: three Adient PO PDFs, the two-FGPN MBOM workbook, and the cutting-report workbook. The disposable local database contains their imported/staged records. PO/BOM/cutting identifiers do not match each other; no associations were invented. Cutting usage needs explicit launch/unit confirmation before posting.

Allocation now uses production remainder, then warehouse, then optional transit arriving by the target date. Launch engineers/managers can edit supplier arrival dates with a recorded reason. The frontend uses Adient branding.

## Verification and boundaries

All **91 backend tests** pass. The frontend production build, changed-file lint, transit-eligibility tests, PostgreSQL migration/reset/import checks, and local HTTP smoke checks pass. **17 existing TypeScript diagnostics remain.** Several screens still use demonstration data, and the browser simulator is not yet connected to the backend simulation calculation. See the issues register before relying on the prototype operationally.

## Repository

- `backend/`: FastAPI services, models, active migrations, and tests.
- `frontend/`: React/TanStack application.
- `docs/`: current documentation and issues register.
- `ressources/business-test/`: current source PDFs and XLSX workbooks.
- `ressources/database/`: historical SQL artifact; not the fresh-install path.
- `archive/`: historical documentation, reports, and older frontend copy.
# PO_ERP_project
