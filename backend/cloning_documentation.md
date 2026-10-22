# Backend Checkout and Setup

Follow the [backend README](README.md) and [technical setup guide](../docs/TECHNICAL_DOCUMENTATION.md#2-runtime-and-local-setup).

`docker compose up -d --build` starts the application at http://localhost:5173 and the API at http://localhost:8080. The backend initializes empty PostgreSQL schemas and upgrades versioned schemas through the supported bootstrap command. Normal startup preserves records.

Source business files are under `../ressources/business-test/`. Explicit reset/seeding is available for disposable development data. The historical SQL artifact under `../ressources/database/` is not the installation path. Remaining problems are in the [issues register](../docs/ISSUES_REGISTER.md).
