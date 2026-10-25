# Frontend Work Remaining

Status reviewed on 21 October 2026. These items are pending; this documentation update does not implement them.

- Resolve the 21 TypeScript diagnostic locations recorded by `tsc --noEmit --incremental false`.
- Connect simulation preview/save/launch to the authoritative backend calculation and records.
- Connect PO correction/validation/import after the existing parse call.
- Replace seeded operational reads and notification-only writes with persisted transactions.
- Integrate stock reception, transit arrivals/corrections, CutMan reports, and final handover processing as backend services become available.
- Align role, user identity, project ownership, units, and document evidence with the agreed business rules.
- Verify reload persistence and the complete role-specific acceptance workflows.

See the [technical issue register](../docs/TECHNICAL_DOCUMENTATION.md#10-problems-and-technical-open-points) and [business acceptance scenarios](../docs/BUSINESS_DOCUMENTATION.md#10-acceptance-scenarios) for evidence and completion criteria.
