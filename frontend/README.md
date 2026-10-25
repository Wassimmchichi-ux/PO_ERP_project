# Adient ERP Frontend

React and TypeScript application using TanStack Start/Router, Vite, Tailwind CSS, reusable UI components, and client-side PDF export.

The frontend uses a standalone Vite configuration and npm with `package-lock.json` as its dependency lockfile. Production builds target a Node server through Nitro.

## Branding

The sidebar, mobile header, login screen, and browser icon use locally stored Adient assets. Product identity and asset paths are centralized in `src/lib/erp/appInfo.ts`.

Official asset sources: [standard logo](https://www.adient.com/wp-content/uploads/2021/09/Adient_Logo.png), [inverse logo](https://www.adient.com/wp-content/uploads/2021/09/Adient_Logo_Inverse.png), and [favicon](https://www.adient.com/wp-content/uploads/2021/10/adient-favicon.png), as used on [Adient's website](https://www.adient.com/).

## Documentation

- [Business workflows and implementation status](../docs/BUSINESS_DOCUMENTATION.md)
- [Technical architecture, simulation, and integration gaps](../docs/TECHNICAL_DOCUMENTATION.md)
- [Technical and business issues only](../docs/ISSUES_REGISTER.md)

## Development

From this directory, with Node.js/npm available:

```bash
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev -- --host 127.0.0.1 --port 5173
```

The frontend reads `VITE_API_BASE_URL`; its default is `http://localhost:8000`. Use `http://localhost:8080` when connecting to the Compose backend. The backend must permit the frontend origin through `ALLOWED_ORIGINS`.

Available checks:

```bash
./node_modules/.bin/tsc --noEmit --incremental false
npm run lint
npm run build
```

To serve the production build:

```bash
node .output/server/index.mjs
```

On 22 October 2026 the build and changed-file lint passed; the full type check still reports eight existing diagnostic locations, with none in the PO-intake route. See the [verification record](../docs/TECHNICAL_DOCUMENTATION.md#9-verification-performed); a successful development preview does not establish type-check or business-workflow correctness.

## Structure

- `src/routes/`: screens and file-based routing.
- `src/components/erp/`: ERP layout, tables, dialogs, and simulation planner.
- `src/components/ui/`: shared interface primitives.
- `src/lib/erp/api.ts`: API base URL, request headers, and error handling.
- `src/lib/erp/session.tsx` and `rbac.ts`: demonstration session and UI capabilities.
- `src/lib/erp/data.ts`: seeded business data used by many screens.
- `src/lib/erp/pdfExport.ts`: browser simulation report generation.
- `src/lib/erp/appInfo.ts`: product identity and attribution.

## Integration status

PO intake now starts with a real PDF chooser, reviews every parsed line with arrow pagination, saves corrections, validates, imports with database references, and downloads the retained original. BOM upload, selected project operations, administration, handover-code access, and customer-delivery operations also have API calls. Many lists and details still read seeded data. Reception confirmation, handover validation, and price edits include notification-only actions; the transit screen reads live stock and persists arrival-date changes with a required reason for launch engineers/managers.

The CutMan screen uses live report upload/history/download and explicit launch/unit confirmation before consumption posting. A staged report does not change stock; duplicate files and events are blocked by the backend.

The browser simulation uses its own calculation and saves into an in-memory array. Future-stock quantities now use live transit entries arriving on or before the required target date; its PO/BOM and current-stock inputs remain seeded. It does not call the backend simulation endpoints. Exported simulation PDFs reflect that browser calculation. The login page selects a seeded user and does not authenticate a password.

Consult the [API/frontend inventory](../docs/TECHNICAL_DOCUMENTATION.md#8-api-and-frontend-integration-inventory) before treating a screen action as a persisted transaction.
