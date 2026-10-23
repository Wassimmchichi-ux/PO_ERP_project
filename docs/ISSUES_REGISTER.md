# Adient ERP — Open Technical and Business Issues

Review date: **23 October 2026**. This file contains unresolved findings in the current working tree. Priorities are: **P0** blocks production use, **P1** must be resolved before an operational pilot, and **P2** is a scale, maintainability, or completeness concern.

The simulation frontend/backend mismatch, extra allocation modes, warehouse-before-production order, project/current-PO/outstanding-demand validation, missing reservations, launch retry idempotency, and basic supplier-arrival separation were addressed in this iteration and are not listed as open defects.

## Technical issues

### TEC-01 — Authentication can be bypassed — P0

Requests without a database identity can fall back to a system actor, and the frontend sends a selectable role header. A caller can therefore claim a role or lose human attribution.

**Effect:** UI role restrictions are not a security boundary, and audit rows may identify the system user instead of the responsible person.

**Required work:** implement password/SSO authentication, signed sessions or tokens, deny anonymous business calls, derive roles server-side, and enforce resource ownership consistently.

**Evidence:** `backend/app/dependencies/auth.py`, `backend/app/policies`, `frontend/src/lib/erp/api.ts`.

### TEC-02 — Material issue is not the complete downstream launch transaction — P0

`launch_saved_simulation` commits allocations and moves warehouse stock, but it does not atomically create all required `Launch`, `LaunchFGPN`, `LaunchPO`, delivery-instruction, receiver, and verification records.

**Effect:** customer delivery and legal handover can require records created separately; a successful issue is not a complete production launch.

**Required work:** define the launch approval request and create the execution, PO/FGPN, stock issue, handover, and evidence records in one transaction or one recoverable saga.

**Evidence:** `backend/app/services/material_simulation_service.py`, models `launch.py`, `launch_fgpn.py`, `launch_po.py`, and `stock_issue_handover.py`.

### TEC-03 — Several screens remain demonstration-backed — P1

Some dashboard, project detail, simulation history/detail, finance, documents, and audit views still read frontend seed arrays or show success without a complete persisted workflow. Stock Monitoring, Warehouse Reception, Transit, Supplier Arrivals, and Stock History now use coordinated database APIs.

**Effect:** users can see data different from PostgreSQL, and some changes disappear on reload.

**Required work:** connect each screen to authoritative list/detail/write APIs, remove remaining seeded operational records, and reload after mutations.

**Evidence:** `frontend/src/lib/erp/data.ts` and the affected routes under `frontend/src/routes`.

### TEC-04 — The optimizer is global per material but has bounded exact roll search — P1

The planner strictly maximizes rows in priority order and aggregates physical demand across all selected POs/FGPNs. For each source/material, roll subset selection is exact only up to 18 rolls and greedy above that threshold. It does not optimize across materials for cost, lateness, setup, reusable remnants, or fairness.

**Effect:** the result is deterministic and aligned with strict priority, but large roll sets or a different business objective may have a better allocation.

**Required work:** approve the current objective and threshold using real cases. If the objective changes, implement a MILP or CP-SAT model with explicit lexicographic weights/constraints and a time limit.

**Evidence:** `backend/app/services/simulation_allocator.py`.

### TEC-05 — Reservation lifecycle lacks automatic housekeeping and user lifecycle APIs — P1

Expired missing-document reservations stop reducing availability and are released when their workflow is touched, but no scheduled job materializes every expired row. Saved simulations also lack complete list/detail/cancel/delete endpoints in the new reservation state machine.

**Effect:** database rows can remain labelled `AWAITING_DOCUMENT` after their effective expiry, and operators lack a normal cancellation interface.

**Required work:** add a periodic expiry task or database job, explicit cancellation with reason, list/detail filters by state, and retention rules. Keep launched rows immutable.

**Evidence:** `release_expired_reservation`, `get_reserved_quantities_by_stock_unit`, and `backend/app/api/simulation.py`.

### TEC-06 — Production ownership and historical consumption remain imperfect — P1

New CutMan rows are tied to a physical stock unit. Historical consumption without a unit is still distributed deterministically across production units of the same material, without reliable owner provenance. There is no complete audited stock reassignment workflow.

**Effect:** owner-specific WIP can be understated or assigned to the wrong unit when legacy data is present.

**Required work:** migrate historical rows where evidence exists, define shared-stock ownership and reassignment authority, and require a stock-unit identifier in future CutMan integrations.

**Evidence:** `_build_pools` in `material_simulation_service.py` and consumption queries in `stock_repository.py`.

### TEC-07 — Supplier arrival supports one final receipt only — P1

Personnel must enter every planned line and team-leader confirmation closes the order. There is no partial receipt across dates, supplier cancellation after arrival entry, correction/reversal after confirmation, or attachment of delivery evidence. The supplier master has a unique administrator-maintained reference, but a separate supplier delivery-note/reference policy is not modeled.

**Effect:** split deliveries and corrected warehouse counts cannot be represented faithfully without editing the plan before confirmation or using manual stock operations.

**Required work:** introduce receipt events and remaining quantities, evidence links, correction/reversal states, supplier-reference rules, and audited cancellation.

**Evidence:** `backend/app/services/supplier_order_service.py` and supplier order models.

### TEC-08 — Notifications are persisted but not fully integrated into the live header — P1

The backend writes notifications for a database user. The frontend's prototype session does not consistently know that user's UUID, and the existing header alerts are seeded.

**Effect:** the legal notification exists in PostgreSQL but may not appear in the responsible engineer's bell during prototype role-only sessions.

**Required work:** complete authentication/user mapping, query `/notifications` from the shell, show unread counts, support marking read, and decide escalation channels.

**Evidence:** `backend/app/models/notification.py`, `backend/app/api/supplier_orders.py`, `frontend/src/components/erp/AppShell.tsx`.

### TEC-09 — Handover proof is not a complete one-time state machine — P1

Signed proof upload, access-code handling, final validation, and stock-unit production receipt are separate. Evidence association and repeat protection are incomplete in parts of the flow.

**Effect:** material can be issued without one reconstructable legal handover chain.

**Required work:** create instructions from the launch, enforce code expiry/use once, bind signed proof to exact issued units, verify the final actor, and transition all units atomically.

**Evidence:** handover API/service and `stock_management_service.confirm_production_handover`.

### TEC-10 — Customer delivery needs a shipment ledger and stronger limits — P1

Delivery quantities accumulate on `LaunchFGPN`; the model retains the latest CMR pointer rather than a complete immutable shipment/line history. Duplicate line handling and concurrent submissions require stronger database protection.

**Effect:** individual shipments and documents are difficult to reconcile, and races can exceed planned quantities.

**Required work:** add shipment and shipment-line entities, unique idempotency keys, row locks/conditional totals, correction events, and PO/launch closure rules.

**Evidence:** `backend/app/services/customer_delivery_service.py` and `backend/app/models/launch_fgpn.py`.

### TEC-11 — Numerical units and roll leftovers are temporary — P1

The user-directed rule treats `total_sqm` as metres. Material types are inferred from type/unit text, source conversion is absent, and whole-roll physical over-issue is reserved/issued without a reusable-remnant process. New BOM materials may have zero price.

**Effect:** material consumption and costing can be wrong once real area, length, layers, scrap, or package conversions are required.

**Required work:** define base units and conversions, coefficient semantics, roll/offcut recovery, precision/rounding, and price-completeness rules.

**Evidence:** demand/pool code in `material_simulation_service.py`, BOM models, and `simulation_allocator.py`.

### TEC-12 — Saved plans are not immutable numerical snapshots — P1

Simulation rows retain selected PO/FGPN quantities and physical allocations but not the exact BOM version or a full input/result snapshot. Replacement review can use today's BOM/master data.

**Effect:** a later replay may differ from the decision reviewed at the meeting.

**Required work:** store BOM-version IDs and normalized demand/result snapshots, hash them, and use the saved snapshot for launch review except where an explicit re-plan is approved.

**Evidence:** `Simulation`, `SimulationFGPN`, and `StockAllocation` models.

### TEC-13 — Document storage and audit attribution need production hardening — P1

Selected flows validate only filenames/extensions, local file writes are not transactional with PostgreSQL, and generic document retrieval/versioning is incomplete. System-user fallback weakens attribution.

**Effect:** missing/orphan files and ambiguous actors can prevent legal reconstruction.

**Required work:** inspect file signatures, use collision-resistant object keys, add malware/size controls, reconcile failed writes, expose authorized download, and record authenticated actors.

**Evidence:** document, handover, PO, BOM, and customer-delivery storage services.

### TEC-14 — Current source documents do not form one material chain — P1

The supplied PO FGPNs do not exactly match the new MBOM FGPNs, and the CutMan material is absent from that MBOM. The CutMan sample also leaves Original/Produced nesting names blank. PO replacement metadata is not yet an executable supersession transaction.

**Effect:** individual parser tests pass, but the sample set cannot prove customer PO → BOM → stock unit → cutting consumption end to end.

**Required work:** supply corresponding source files or approve explicit revision/project mappings. Define how replacement POs reduce or supersede outstanding demand.

**Evidence:** `ressources/business-test` and document-compatibility tests.

### TEC-15 — Commercial approval and finance remain incomplete — P1

Approval limits exist in policy helpers, but PO import is not a persisted commercial approval. Finance pages still rely on demonstration values and do not represent invoice/payment ledgers.

**Effect:** an imported PO is not proof of commercial approval, and displayed financial totals are not accounting records.

**Required work:** implement amount/currency approval transactions, persisted pricing responsibility, shipment-based revenue/cost reporting, and separate invoice/payment states.

**Evidence:** policy rules, PO import service, and `frontend/src/routes/finance.tsx`.

### TEC-16 — Frontend bundle size should be reduced — P2

The production build passes, but Vite reports chunks above 500 kB, mainly around PDF/canvas libraries and the main client bundle.

**Effect:** slower initial loading on constrained warehouse devices.

**Required work:** lazy-load PDF export and heavy routes, split vendor chunks, and measure real device performance.

## Business decisions still required

| ID / priority | Decision | Why it matters | Suggested owner |
| --- | --- | --- | --- |
| **BIZ-01 / P0** | Approve one role/action/project matrix and real authentication method. | Server and browser cannot enforce legal responsibility until identity is trusted. | Plant Manager, IT/security. |
| **BIZ-02 / P0** | Define the full launch approval and handover authority. | Stock issue currently ends before the complete legal production record. | Launch Manager, warehouse, production. |
| **BIZ-03 / P1** | Confirm strict priority as the optimizer objective, or provide weights for output, due date, waste, and fairness. | Different objectives produce different “best” selections. | Planning and Launch Manager. |
| **BIZ-04 / P1** | Confirm the 24 elapsed-hour missing-document deadline, cancellation authority, and holiday behavior. | Reservations must neither disappear too early nor block stock indefinitely. | Launch Manager, quality/legal. |
| **BIZ-05 / P1** | Define partial supplier receipt, tolerance, evidence, correction, and cancellation rules. | The current workflow closes one complete receipt. | Warehouse Team Leader, Launch Engineer. |
| **BIZ-06 / P1** | Approve base units and replace the temporary `total_sqm = metres` rule. | Planning quantities cannot be certified without dimensional meaning. | Industrial engineering. |
| **BIZ-07 / P1** | Decide ownership/reassignment rules for global, engineer, warehouse, and production stock. | Availability and accountability depend on a single ownership model. | Warehouse and Launch Manager. |
| **BIZ-08 / P1** | Define whole-roll excess and reusable offcut policy. | Whole issue can physically exceed demand and affect later availability. | Warehouse and production. |
| **BIZ-09 / P1** | Define immutable evidence and retention for PO, BOM, meeting, supplier receipt, handover, CutMan, and CMR records. | Audit/legal reconstruction needs a complete versioned chain. | Quality/legal and IT. |
| **BIZ-10 / P1** | Supply matching documents or approve master-data/revision mapping and PO supersession behavior. | Current source files cannot demonstrate one end-to-end job. | Master-data owner and Launch Engineer. |
| **BIZ-11 / P1** | Define shipment correction, PO closure, invoice, and payment rules. | Delivery and finance cannot be reconciled without these states. | Logistics and finance. |
