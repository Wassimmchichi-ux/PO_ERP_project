# Detected technical and business issues

Review date: 22 October 2026. This register describes remaining issues found in the current source and supplied business documents. Findings are from source inspection unless an executed example is explicitly stated. Priorities: **P0** blocks relying on the application for access control or material execution; **P1** needs resolution before an operational pilot; **P2** affects traceability, maintenance, or scale. Business decisions are identified separately from implementation defects.

## Technical issues

### TEC-01 — Unauthenticated callers can obtain privileged access — P0

**Finding:** Requests without identity headers become a system actor, which bypasses permission checks. Clients can also supply their own role header. Administration, projects, delivery, handover, and stock reads do not consistently require a policy actor. The frontend sends a selected demonstration role rather than authenticated identity.

**Consequence:** Hiding a screen or button does not prevent direct API access, and a recorded action cannot reliably identify the person responsible.

**Required fix:** Authenticate users, deny unauthenticated access by default, authorize every resource operation on the server, and keep explicit service identities separate from human sessions.

**Evidence:** [identity dependency](../backend/app/dependencies/auth.py), [system bypass](../backend/app/policies/engine.py), [administration API](../backend/app/api/admin.py), [frontend API headers](../frontend/src/lib/erp/api.ts).

### TEC-02 — Project scope and role rules disagree across interfaces — P1

**Finding:** Frontend project restrictions depend on assigned-user arrays, while the database project has one engineer-owner field. Simulation accepts a `project_id` but does not use it to restrict PO/FGPN selections; a supplied stock owner is not checked against the requesting user. Frontend administrators are excluded from business data, whereas backend administrators have all permissions.

**Consequence:** Users can work outside the project or stock scope suggested by the interface. Assignments and capabilities can change meaning between screens and API requests.

**Required fix:** Agree the role and assignment model, enforce project membership and owner scope on the server, and test cross-project access. See BIZ-01 and BIZ-02.

**Evidence:** [frontend capabilities](../frontend/src/lib/erp/rbac.ts), [Project model](../backend/app/models/project.py), [preview validation](../backend/app/services/material_simulation_service.py), [backend permissions](../backend/app/policies/permissions.py).

### TEC-03 — Several screens report success without persistent transactions — P0

**Finding:** Browser simulation saving inserts a record into the imported `simulations` array. Reception posting and reception correction display success notifications without saving the transaction. Finance price changes also display success without persistence. Seeded records remain the source for several lists and details.

**Consequence:** Work can disappear after reload, and the interface can show balances or decisions unrelated to the database.

**Required fix:** Connect each accepted workflow to a persisted API transaction and reload its authoritative record. Identify any retained demonstration data clearly; never report an unpersisted operation as completed.

**Evidence:** [simulation save handler](../frontend/src/routes/simulations.new.tsx), [reception confirmation handlers](../frontend/src/routes/stock.reception.tsx), [finance price handler](../frontend/src/routes/finance.tsx), [seed data](../frontend/src/lib/erp/data.ts).

### TEC-04 — Browser and backend simulations can produce different decisions — P0

**Finding:** The browser combines seeded warehouse/BOM data with live eligible transit rows, counts WIP only through the global-stock toggle, and deducts full requested material quantities while processing priorities. The backend calculates material bottlenecks and allocates physical units with whole-roll rules. The browser does not request the backend preview calculation.

**Consequence:** A browser result or PDF can disagree with the backend about feasible quantities, shortages, owner scope, and stock to issue. Implementing source priority in the backend alone does not make the browser calculation equivalent.

**Required fix:** Use the backend preview as the authoritative calculation and display/export its results. Verify shared examples for WIP, whole rolls, partial coverage, owner scope, and multiple POs.

**Evidence:** [browser calculation](../frontend/src/routes/simulations.new.tsx), [backend demand construction](../backend/app/services/material_simulation_service.py), [allocator](../backend/app/services/simulation_allocator.py).

### TEC-05 — Feasibility flags can contradict actual allocations — P0

**Finding, reproduced:** `MANUAL` with a missing material pool returns fully covered/100% although launchable quantity is zero and there are no allocations. An unsupported strategy string produces the same inconsistency because the request accepts any string. With two indivisible rolls of 10 and two demands of 11 and 9, `MANUAL` issues both rolls to the first demand; the second still reports 100%/fully covered while its launchable quantity is zero. An empty positive-demand BOM can also pass as feasible. Duplicate selections, explicitly supplied older PO lines, and quantities above outstanding PO demand are not comprehensively rejected.

**Consequence:** A positive feasibility indicator is not sufficient evidence that the requested output can be produced.

**Required fix:** Constrain strategies, calculate shortages from actual allocations for every demand, validate usable BOM content and current outstanding demand, and require consistent coverage flags/quantities in all strategies.

**Evidence:** [request schema](../backend/app/schemas/simulation.py), `run_allocation_engine` in [allocator](../backend/app/services/simulation_allocator.py), [selection validation](../backend/app/services/material_simulation_service.py).

### TEC-06 — Launch review does not revalidate or commit production remainder — P0

**Finding:** Production remainder is represented by a virtual slot without a stock-unit ID. Save and launch discard allocations without physical IDs. If saved physical allocations are available, launch review returns success without rechecking the complete saved feasibility or current WIP. A simulation supported entirely by WIP can have no saved physical allocations to check.

**Consequence:** The same remainder can support multiple launches, or a launch can be accepted after the production remainder has been consumed. Prioritizing production remainder makes this accounting gap particularly significant.

**Required fix:** Persist and account for the commitment of production quantities, revalidate the complete approved demand at execution, and explicitly distinguish an authorized partial launch from an infeasible plan. See BIZ-02 and BIZ-03.

**Evidence:** `_build_pools`, `save_simulation`, `_launch_allocations_from_preview`, and `review_simulation_for_launch` in [simulation service](../backend/app/services/material_simulation_service.py).

### TEC-07 — Material issue does not create the downstream launch records — P0

**Finding:** `launch_saved_simulation` changes stock and creates `LAUNCH` allocation rows, but does not create `Launch`, `LaunchFGPN`, `LaunchPO`, or a handover instruction. Customer delivery requires the separate launch records.

**Consequence:** Successful material issue does not by itself produce a complete production-to-delivery chain. Downstream operations can require records created separately.

**Required fix:** Create the execution records and their approved PO/FGPN quantities in one consistent launch transaction, with links to stock issue, receiver, evidence, and handover.

**Evidence:** [launch operation](../backend/app/services/material_simulation_service.py), [Launch model](../backend/app/models/launch.py), [delivery service](../backend/app/services/customer_delivery_service.py).

### TEC-08 — Repeated or concurrent launches can compete for the same stock — P0

**Finding:** Saving does not reserve stock. Issue performs ordinary reads and writes without row locking or an equivalent conditional update, and has no explicit already-launched/idempotency guard. After a component split, the remaining original unit may still satisfy a repeated request; reallocation can also select fresh stock for a repeated launch.

**Consequence:** Two users can promise the same material, and a retried request can issue material more than once.

**Required fix:** Define the reservation point and expiry/cancellation rules, protect stock updates atomically, and make launch execution idempotent. Test competing transactions against PostgreSQL. See BIZ-03.

**Evidence:** [stock read/issue functions](../backend/app/repositories/stock_repository.py), [save/launch service](../backend/app/services/material_simulation_service.py), [allocation persistence](../backend/app/repositories/simulation_repository.py).

### TEC-09 — Owner-specific balances and owner assignment are incomplete — P1

**Finding:** Owner-scoped production receipts subtract consumption aggregated across all owners. Owner/global production quantities are combined into one virtual remainder. Reception with an owner requires both `stock.receive` and `stock.assign_owner`; ordinary warehouse roles have only the former, and launch roles only the latter. There is no separate stock reassignment operation.

**Consequence:** An engineer's available WIP can be understated or misattributed, and the intended warehouse-to-owner assignment workflow is blocked for normal roles.

**Required fix:** Define consumption attribution and global-stock treatment, calculate balances on the same scope, and provide an authorized assignment/reassignment workflow. See BIZ-02.

**Evidence:** [consumption aggregation](../backend/app/repositories/stock_repository.py), [pool construction](../backend/app/services/material_simulation_service.py), [reception checks](../backend/app/services/stock_management_service.py), [permissions](../backend/app/policies/permissions.py).

### TEC-10 — Physical arrival and handover are not a complete verified stock lifecycle — P1

**Finding:** An eligible `IN_TRANSIT` unit can be issued without proof of physical warehouse receipt; the stock API has no transit-arrival/partial-arrival transaction. Handover has no creation or final-validation endpoint. Signed-proof upload does not apply the open/confirm expiry guard; confirmation can repeat. Production receipt accepts a document ID without checking that it is the validated proof for that stock unit's handover.

**Consequence:** Planning availability can be mistaken for physical availability, and stock can move to production without a complete associated proof chain.

**Required fix:** Implement receipt and partial-receipt movements, enforce the agreed handover state machine, and validate evidence association and one-time receipt. See BIZ-04 and BIZ-07.

**Evidence:** [stock API](../backend/app/api/stock.py), [issue/receipt transitions](../backend/app/repositories/stock_repository.py), [handover API](../backend/app/api/handover.py), [handover service](../backend/app/services/handover_service.py), [production receipt](../backend/app/services/stock_management_service.py).

### TEC-11 — Customer delivery can exceed planned quantities and loses shipment-level detail — P1

**Finding:** Duplicate line IDs in one delivery are each validated against the original remaining quantity, then accumulated. Delivery updates are not protected against concurrent submissions. The launch stores the latest CMR pointer and cumulative quantities without a separate shipment-line ledger or corresponding PO closure transaction.

**Consequence:** Repeated lines can over-deliver, and the source of cumulative deliveries and individual transport documents is difficult to reconcile.

**Required fix:** Reject or aggregate duplicate lines before validation, enforce quantity limits atomically, retain each shipment and CMR association, and reconcile launch and PO balances. See BIZ-08.

**Evidence:** [delivery request](../backend/app/schemas/customer_delivery.py), [validation and accumulation](../backend/app/services/customer_delivery_service.py), [launch quantities](../backend/app/models/launch_fgpn.py).

### TEC-12 — Evidence and audit attribution are insufficient for reconstruction — P1

**Finding:** Handover and customer-delivery writes use the system user; the supplied uploader name is merely text. Their PDF checks inspect the filename extension, and filesystem writes occur separately from database commits. Repeated uploads in the same second can reuse a stored filename. There is no generic document list/download API. Saved simulations do not preserve a full BOM/input snapshot, and their stored allocation rows do not identify the FGPN that consumed each quantity.

**Consequence:** A decision or stock movement cannot always be reconstructed from retrievable originals, immutable inputs, and a verified actor. Failed transactions can leave orphan files.

**Required fix:** Associate authenticated actors, retain versioned inputs and retrievable source evidence, validate uploaded content, use unique storage keys, and reconcile file/database failures. See BIZ-09.

**Evidence:** [handover storage/audit](../backend/app/services/handover_service.py), [delivery storage/audit](../backend/app/services/customer_delivery_service.py), [registered APIs](../backend/app/main.py), [Simulation](../backend/app/models/simulation.py), [StockAllocation](../backend/app/models/stock_allocation.py).

### TEC-13 — Numerical meaning is not fully enforced by the simulation contract — P1

**Finding:** Material demand uses `total_sqm` for type `M` and `total_quantity` for other types. The workbook coefficient is stored separately but not applied by demand construction. Finished-good quantities can be fractional; the safety coefficient accepts any positive value, including values below one. Roll handling is inferred from material type/unit text. New BOM materials receive a zero unit price.

**Consequence:** Correctly parsed numbers can still lead to incorrect material consumption, indivisible output, or financial totals unless their business meaning is agreed.

**Required fix:** Establish explicit base units, conversions, coefficient semantics, indivisibility/rounding rules, and a completeness rule for prices. Validate approved numerical examples. See BIZ-05 and BIZ-06.

**Evidence:** [demand construction and roll classification](../backend/app/services/material_simulation_service.py), [quantity schema](../backend/app/schemas/simulation.py), [BOM/material persistence](../backend/app/repositories/bom_repository.py).

### TEC-14 — Commercial approval and finance are not complete persisted workflows — P1

**Finding:** PO approval limits exist as policy helpers, but the PO import path checks `po.import`, not an approval transaction. There is no persisted approval endpoint applying those amount thresholds. Finance calculations and manual price edits use frontend seed data.

**Consequence:** A parsed/imported PO is not evidence of commercial approval, and displayed finance figures are not an accounting record.

**Required fix:** Implement the agreed approval transaction and amount/currency basis, connect price maintenance and delivery-based financial reporting to persisted data, and distinguish delivery from invoicing/payment. See BIZ-01 and BIZ-08.

**Evidence:** [approval limits](../backend/app/policies/rules.py), [PO import service](../backend/app/services/parsed_purchase_order_service.py), [PO API](../backend/app/api/parsed_purchase_order.py), [finance screen](../frontend/src/routes/finance.tsx).

### TEC-15 — Frontend type checking still fails — P1

**Finding, executed:** The frontend production build succeeds, but `tsc --noEmit --incremental false` reports 17 diagnostic locations in the existing planner, admin mapping, BOM selection, delivery/handover, PO intake, and project mapping. These include possibly undefined array entries, exact-optional-property mismatches, and index-signature access.

**Consequence:** A successful bundle is not a clean static-validation baseline; nullable/API mapping errors can remain hidden until a specific workflow executes.

**Required fix:** Resolve the remaining contracts and optional-value handling, then require type checking alongside the build. The changed transit/cutting integration does not account for these existing diagnostics.

**Evidence:** [frontend source](../frontend/src), [TypeScript configuration](../frontend/tsconfig.json); command executed 22 October 2026.

### TEC-16 — Saved simulation lifecycle and numerical replay are incomplete — P2

**Finding:** Save enforces a 100-simulation limit per user, but there are no list/detail/delete endpoints. Replacement review uses the current BOM rather than the saved BOM version. Request coefficients have unrestricted decimal precision, while saved coefficients use `Numeric(5, 2)`. A view-only reviewer can reach a replacement-preview path requiring `simulation.run`.

**Consequence:** Users can reach a save limit without an API cleanup path; replay may change the result; a review operation can fail only when replacement stock becomes necessary.

**Required fix:** Provide the intended lifecycle operations and retention rules, retain versioned inputs with consistent precision, and define permissions for replacement review independently of interactive simulation. See BIZ-09.

**Evidence:** [simulation API](../backend/app/api/simulation.py), [save/review implementation](../backend/app/services/material_simulation_service.py), [persisted coefficient](../backend/app/models/simulation.py).

### TEC-17 — Document identities do not establish an executable material chain — P1

**Finding:** The supplied PO lines have no exact FGPN match with the two new BOM codes (`6134635-AD40-000`, `6134635-AT43-000`). Cutting material `6718062-180020-D` is absent from that BOM. PO 2301478532 says it replaces 2301475999, but that reference remains parser metadata rather than a supersession transaction. The BOM repeats shared material codes with conflicting descriptions; the first description remains in the master.

**Consequence:** Successful imports alone cannot connect these samples into a valid PO-to-BOM-to-consumption simulation. Old order demand can remain active after replacement, and conflicting labels can mislead operators.

**Required fix:** Confirm the intended sample relationships, implement explicit customer/BOM revision mapping where needed, define replacement-order effects on outstanding demand, and surface master-data conflicts for review. Do not infer matches from similar-looking codes.

**Evidence:** [business-test sources](../ressources/business-test), [compatibility tests](../backend/tests/test_po_parser_simulation_compatibility.py), [PO parser](../backend/app/services/parsed_purchase_order_service.py), [BOM persistence](../backend/app/repositories/bom_repository.py).

### TEC-18 — Cutting-consumption correction and assignment remain incomplete — P1

**Finding:** Staging preserves originals and posting checks launch existence, material/unit compatibility, sufficient WIP, and duplicates. The source has no launch or unit identifier, so posting depends on manual confirmation. There is no reversal/amendment workflow, owner attribution, or validation that the selected launch's approved BOM contains each reported material. Event fingerprints rely on material/time/equipment/nesting fields, several of which are blank in the sample.

**Consequence:** Incorrect confirmed assignments need manual investigation; an ambiguous repeated event is blocked rather than automatically corrected. Existence of a launch is not proof that the cutting activity belongs to it.

**Required fix:** Agree source event identifiers, launch/material mapping and consumption meaning; add audited reversal/amendment and appropriate assignment validation. Keep unresolved reports staged.

**Evidence:** [cutting service](../backend/app/services/cutting_report_service.py), [extractor](../backend/app/utils/cutting_report_extractor.py), [source report](../ressources/business-test/cutting_report-test%20.xlsx).

## Business issues and decisions

| ID / priority | Unresolved issue and operational consequence | Decision or completion required | Suggested accountable roles / evidence |
| --- | --- | --- | --- |
| **BIZ-01 / P0** | Responsibilities are not represented consistently: administrator business access, engineer launch approval, project membership, and PO approval amounts differ across layers. An authorization shown in the UI may not match the API. | Approve one role/action/project matrix; define who approves a launch and whether the PO amount basis includes tax and which currency applies. | Plant Manager + Launch Manager; TEC-01, TEC-02, TEC-14. |
| **BIZ-02 / P1** | Stock is assigned to users, while consumption is aggregated by material. It is unclear how owner stock, enterprise stock, and shared production remainder should be reconciled. | Define ownership and reassignment responsibilities, consumption attribution, treatment of shared remainder, and the usable warehouse assignment process. | Launch Manager + warehouse + production; TEC-06, TEC-09. |
| **BIZ-03 / P0** | Multiple plans can rely on the same warehouse or production quantities; partial feasibility is not a complete authorization to launch. | Choose when stock becomes committed, how reservations expire/cancel, whether partial launches are permitted, and how remaining PO demand is reduced. | Planning + Launch Manager + warehouse; TEC-05–TEC-08. |
| **BIZ-04 / P1** | A supplier ETA is a planning promise, not evidence of actual receipt. Partial deliveries, late physical arrival, receipt corrections, and cancellation need an agreed stock movement process. | Define receipt-before-issue policy, partial-receipt quantities, required supplier evidence, and who confirms/corrects each movement. | Warehouse Team Leader + Launch Engineer; TEC-10. |
| **BIZ-05 / P1** | The new MBOM contains source-unit information alongside a `Total sqm` quantity; the intended relation between source unit, area, coefficient, and simulation allowance needs confirmation. The cutting report's `Spreading Usage` and `CNC Length` cannot be treated as interchangeable consumption measures. | Confirm each source field's unit and meaning, the stock base unit, any conversion factors/layers, whether the workbook coefficient is already included, and the allowed safety coefficient. | Industrial engineering + production; [current business documents](../ressources/business-test), TEC-13. |
| **BIZ-06 / P1** | Whole-roll issue can consume more than demand; component and finished-piece rounding and treatment of leftovers are not fully agreed. New materials may have no usable cost. | Define roll/package granularity, reusable/offcut quantities, piece rounding, material price ownership, and when costing must be blocked for missing prices. | Warehouse + industrial engineering + finance; TEC-04, TEC-05, TEC-13. |
| **BIZ-07 / P1** | The handover code/proof process lacks a complete operational authority and state sequence. A name typed into a form is not verified receipt responsibility. | Assign code generation, expiry, reuse rules, signed-proof review, final validation, and the moment production becomes responsible for the stock. | Warehouse Team Leader + Launch Manager + manufacturing receiver; TEC-10, TEC-12. |
| **BIZ-08 / P1** | Partial deliveries, repeated CMRs, transport costs, customer acceptance, PO closure, and financial follow-up are not represented as one reconciled history. | Define shipment-level evidence and quantities, correction/cancellation rules, closure criteria, and the distinction between delivery, invoice, and payment. | Logistics + finance + Launch Manager; TEC-11, TEC-14. |
| **BIZ-09 / P2** | Required evidence, meeting-minute timing, input versions, retention, and simulation deletion rules are not settled. A stored file reference is not sufficient to reproduce a decision. | Specify which originals and approvals must be retained, whether minutes are required at save or approval, who may correct/delete records, and the retention period. | Business owner + Launch Manager + administrator; TEC-12, TEC-16. |
| **BIZ-10 / P1** | The supplied cutting workbook contains one populated data row but does not identify the launch, owner, nesting, layers, or operational completion status. A report row cannot establish a launch-specific consumption transaction or remaining WIP by itself. | Confirm whether each report is a cumulative snapshot or event ledger, select the consumption basis and unit, supply/confirm the launch linkage, and agree correction/reversal handling. Identical-file and overlapping-event duplicates are blocked, but ambiguous events and incorrect assignments require review. | Production + integration owner; [cutting workbook](../ressources/business-test/cutting_report-test%20.xlsx), TEC-06, TEC-09, TEC-18, BIZ-05. |
| **BIZ-11 / P1** | The supplied POs, BOM finished goods, and cutting material do not match. Imported files cannot demonstrate the complete order-to-consumption workflow together. | Supply the intended corresponding samples or approve explicit customer/BOM/material mappings, including revision validity and project scope. | Launch Engineer + master-data owner; TEC-17. |
| **BIZ-12 / P1** | A PO replacement reference and conflicting descriptions for shared BOM materials do not have an agreed resolution process. | Define whether replacement cancels prior demand, preserves completed deliveries, or creates a new revision; assign authority for conflicting master descriptions. | Commercial owner + Launch Manager + master-data owner; TEC-17. |
