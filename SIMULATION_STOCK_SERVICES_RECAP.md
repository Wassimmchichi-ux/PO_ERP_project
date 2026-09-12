# Simulation And Stock Services Recap

This recap summarizes the current simulation, stock, PO/FGPN, and test changes so the next implementation step can be reviewed deliberately.

## 1. Target Workflow

The launch engineer does not simulate all FGPNs in a PO. The simulation request is now an ordered priority list of selected entries:

```text
PO + FGPN + requested quantity
```

The simulation uses that priority order to satisfy higher-priority FGPN demand first, then lower-priority demand with the remaining stock.

The expected business flow is:

1. Launch engineer selects PO+FGPN rows and quantities.
2. System previews feasibility using BOM demand, WIP, warehouse stock, and optionally in-transit stock.
3. Launch engineer saves the simulation.
4. Launch engineer uploads a draft simulation/meeting document.
5. After meeting approval, the launch is reviewed again against current stock availability.
6. If the original simulated stock units are still available, launch uses them.
7. If some simulated stock units were already consumed by another launch, the system searches for replacement stock units.
8. If replacement stock can satisfy the same saved launch quantities, launch can proceed.
9. If not, the system blocks the launch and reports the stock conflict/shortfall.
10. Warehouse issues materials to production.
11. Production signs a handover document.
12. Warehouse uploads the signed handover document and stock moves from `ISSUED_TO_PRODUCTION` to `PRODUCTION`.

## 2. Service Boundaries

The service folder should contain business logic only. Direct database querying was moved into repositories.

Current boundary:

- Services orchestrate workflow and business rules.
- Repositories talk directly to SQLAlchemy models and the database.
- The allocator is pure in-memory logic.

The service query-boundary scan currently shows only `Session` type imports in services, not direct SQLAlchemy query/model usage.

## 3. Simulation Service

Main file:

- `backend/app/services/material_simulation_service.py`

Responsibilities:

- Accept an ordered list of selected `PO + FGPN + quantity` entries.
- Resolve the current PO line for each PO+FGPN through the repository.
- Validate explicit `po_line_id` values when provided.
- Load active BOM lines for the selected FGPNs.
- Calculate material demand:
  - Material type `M`: demand uses `total_sqm`.
  - Material type `S`: demand uses `total_quantity`.
- Build stock pools from:
  - Warehouse stock units.
  - In-transit stock units when requested.
  - WIP/production stock from remaining production consumption.
- Run the priority allocation algorithm.
- Return per-FGPN feasibility, material usage, shortfalls, and suggestions.
- Save simulations without creating a launch.
- Review a saved simulation before launch.
- Launch a saved simulation only after feasibility is reviewed against current stock.

Important launch behavior:

- Simulation allocations do not mutate stock.
- Launch allocations mutate stock by issuing stock units to production.
- `ISSUED_TO_PRODUCTION` stock is excluded from future simulations.
- Only stock with status `PRODUCTION` is treated as WIP available for remaining production consumption.

## 4. Simulation Allocator

Main file:

- `backend/app/services/simulation_allocator.py`

The allocator is pure logic. It works on `StockSlot` objects and returns simulated allocation decisions.

Important `StockSlot` fields:

- `quantity`: mutable remaining quantity in the simulation snapshot.
- `initial_quantity`: original slot quantity for audit/reporting.
- `material_type`: material type such as `M` or `S`.
- `can_split`: whether the slot can be partially consumed.
- `available`: whether the slot is usable.
- `expected_arrival_date`: used for in-transit visibility.

Removed concept:

- `allocated: Decimal = Decimal("0.0000")`

Reason:

- Allocation is not tracked as a mutable field on the stock slot.
- During simulation, `quantity` is reduced inside the in-memory copy.
- For actual launch, the real `StockUnit` state is changed by repository logic.

Material rules:

- Rolls/material type `M` cannot be cut.
- A roll stock unit is all-or-nothing.
- If a 60m roll is used to satisfy 50m demand, material coverage is 50m but the physical issued quantity is 60m.
- Components/accessories/material type `S` can be partially issued from a package.
- A package of 50 components can issue 7 components and leave 43 in warehouse or in transit.
- Production WIP is splittable because it represents remaining consumable production quantity.

Allocation strategy:

- Higher-priority FGPNs consume stock first.
- The allocator first computes the launchable quantity for each FGPN from all required material pools.
- It then allocates only the materials needed for that launchable quantity.
- This avoids over-allocating non-limiting materials when another material causes the shortfall.
- For whole rolls, it tries to find the smallest sufficient whole-slot combination.
- For up to 18 whole slots it uses exhaustive combination search.
- For larger sets it falls back to a greedy approach.

## 5. Stock Management Service

Main file:

- `backend/app/services/stock_management_service.py`

Responsibilities:

- Return stock summaries and material-level stock details.
- Separate warehouse, in-transit, issued, and production quantities.
- Treat only `PRODUCTION` status as WIP available to simulation.
- Exclude `ISSUED_TO_PRODUCTION` from simulation availability.
- Orchestrate production handover confirmation through the stock repository.

Status meaning:

- `WAREHOUSE`: physically available in warehouse.
- `IN_TRANSIT`: not yet received but optionally usable in simulation planning.
- `ISSUED_TO_PRODUCTION`: launch approved and warehouse has reserved/issued the material, but production has not yet signed receipt.
- `PRODUCTION`: production engineer has signed receipt; material is now production WIP.

## 6. Stock Unit Split And Handover Logic

Main repository:

- `backend/app/repositories/stock_repository.py`

Stock unit launch issue behavior:

- Whole roll issue:
  - Original stock unit moves to `ISSUED_TO_PRODUCTION`.
  - Quantity stays unchanged for traceability.
  - No child stock unit is created.

- Exact component package issue:
  - Original stock unit moves to `ISSUED_TO_PRODUCTION`.
  - Quantity stays unchanged because the full package was issued.
  - No child stock unit is created.

- Partial component package issue:
  - Parent stock unit remains in its original available status.
  - Parent quantity is reduced by the issued quantity.
  - A child stock unit is created for the issued quantity.
  - Child status is `ISSUED_TO_PRODUCTION`.
  - Child points to `parent_stock_unit_id` for audit traceability.

Production handover:

- Warehouse uploads/links a signed handover document.
- The issued stock unit moves from `ISSUED_TO_PRODUCTION` to `PRODUCTION`.
- The stock unit stores `handover_document_id`.
- The stock unit stores `received_by_production_at`.

## 7. Repositories

### Simulation Repository

Main file:

- `backend/app/repositories/simulation_repository.py`

Responsibilities:

- Resolve selected PO+FGPN rows.
- Validate PO line ownership.
- Load current active BOM lines.
- Save simulation headers.
- Save selected simulation FGPN rows.
- Save stock allocation records.
- Load saved simulation data for launch review.

### Stock Repository

Main file:

- `backend/app/repositories/stock_repository.py`

Responsibilities:

- Fetch available stock units.
- Fetch production WIP stock.
- Calculate material stock details.
- Issue stock units to production.
- Split partial component packages.
- Mark issued stock units as received by production after handover.

### BOM Repository

Main file:

- `backend/app/repositories/bom_repository.py`

Responsibilities:

- Persist BOM versions and BOM lines.
- Resolve active BOM versions.
- Create/update material definitions.
- Assign material type from BOM line part type:
  - `M` -> material type `M`, unit `sqm`.
  - `S` -> material type `S`, unit `pcs`.

### Parsed Purchase Order Repository

Main file:

- `backend/app/repositories/parsed_purchase_order_repository.py`

Responsibilities:

- Store parser output in `ParsedPurchaseOrder.parsed_payload`.
- Store only launch-engineer correction diffs in `ParsedPurchaseOrderCorrection`.
- Reload parsed PO records with their corrections for review screens.
- Mark parsed PO staging records as `PARSED`, `CORRECTED`, or `VALIDATED`.
- Import the effective corrected payload into real PO tables after validation.
- Resolve each parsed PO line `part_number` against `FGPN` by `project_id + fgpn_code`.
- Create missing FGPN rows for the selected project.
- Update existing FGPN unit prices and add `FGPNPriceHistory` rows when PO unit price changes.

The parsed PO service applies correction diffs to produce an effective payload for the UI and validation. The import endpoint then writes `PurchaseOrder`, `PurchaseOrderVersion`, and `PurchaseOrderLine` rows.

## 8. Data Model And Migrations

### Parsed Purchase Order Staging

New staging tables:

- `ParsedPurchaseOrder`
- `ParsedPurchaseOrderCorrection`

Purpose:

- Keep the full original parser output.
- Store only corrected fields with original and corrected values.
- Support the launch-engineer review page before final PO validation/import.

Important fields:

- `ParsedPurchaseOrder.parsed_payload`
- `ParsedPurchaseOrder.status`
- `ParsedPurchaseOrder.validated_po_id`
- `ParsedPurchaseOrderCorrection.field_path`
- `ParsedPurchaseOrderCorrection.original_value`
- `ParsedPurchaseOrderCorrection.corrected_value`
- `ParsedPurchaseOrderCorrection.confirmed`

Migration:

- `backend/migrations/versions/c2f9a6b4d1e3_add_parsed_po_staging.py`
- `backend/migrations/versions/d9e8a7c6b5f4_add_po_import_constraints.py`

Import behavior:

- `PurchaseOrder.current_version_id` is nullable while the PO header is first created, then set to the created version.
- `FGPN` has a unique project-scoped index on `project_id + fgpn_code`.
- Parsed PO `part_number` becomes the project-scoped `FGPN.fgpn_code`.
- New part numbers create new FGPN records.
- Existing FGPN price changes update `FGPN.unit_price` and create `FGPNPriceHistory`.

Simulation/launch relationship:

- `Simulation` is the prelaunch planning record.
- Saved simulations no longer store `launch_id`.
- `Launch` is created only after approval.
- `Launch.simulation_id` is the required unique FK back to the approved simulation.

### SimulationFGPN

New model/table to persist selected simulation entries:

- `simulation_id`
- `po_id`
- `fgpn_id`
- `po_line_id`
- `priority`
- `po_quantity`
- `simulation_quantity`
- `launchable_quantity`
- `created_at`

Migration:

- `backend/migrations/versions/7f4c58d12a31_add_simulation_fgpn_po_selection.py`

### StockAllocation

New fields:

- `allocation_type`
  - `SIMULATION`: planned allocation for saved simulation/audit.
  - `LAUNCH`: actual allocation that issues stock to production.
- `is_whole_issue`
  - Records whether the physical stock unit was consumed as a whole.

Migration:

- `backend/migrations/versions/94f3a91bd2c8_add_stock_allocation_type.py`

### StockUnit

New fields:

- `parent_stock_unit_id`
- `handover_document_id`
- `issued_to_production_at`
- `received_by_production_at`

New relationships:

- `parent_stock_unit`
- `split_children`
- `handover_document`

Migration:

- `backend/migrations/versions/1c4b0dbabc9f_add_stock_unit_split_handover.py`

The raw SQL snapshot was also updated:

- `PO_database.sql`

## 9. API Endpoints

Simulation endpoints:

- `POST /simulations/preview`
- `POST /simulations`
- `POST /simulations/{simulation_id}/launch-review`
- `POST /simulations/{simulation_id}/launch`

Stock endpoints:

- `GET /stock/summary`
- `GET /stock/production`
- `GET /stock/in-transit`
- `GET /stock/materials/{mpn}`
- `POST /stock/units/{stock_unit_id}/production-handover`

Parsed PO endpoints:

- `POST /purchase-orders/parsed`
- `POST /purchase-orders/parsed/upload-json`
- `GET /purchase-orders/parsed/{parsed_po_id}`
- `PUT /purchase-orders/parsed/{parsed_po_id}/corrections`
- `POST /purchase-orders/parsed/{parsed_po_id}/validate`
- `POST /purchase-orders/parsed/{parsed_po_id}/import`

Dashboard endpoint touched by stock status logic:

- `GET /dashboard`

## 10. Test Coverage

### Allocator Tests

File:

- `backend/tests/test_simulation_allocator.py`

Covered cases:

- Exact allocation.
- Greedy allocation.
- Insufficient stock.
- Priority allocation.
- Manual quantity allocation.
- Priority plus manual quantity.
- No over-allocation of non-limiting materials.
- Whole roll cannot be split.
- Whole roll allocation chooses smallest sufficient combination.
- Launch issue reduces component stock by creating a child stock unit.
- Whole roll launch marks the original stock unit `ISSUED_TO_PRODUCTION` and keeps quantity unchanged.

### Demand And Pool Tests

File:

- `backend/tests/test_simulation_demand.py`

Covered cases:

- Material type `M` demand uses `total_sqm`.
- Material type `S` demand uses `total_quantity`.
- Selected PO+FGPN priority reports expected launchable quantities.
- Pool builder marks roll materials as whole-issue.
- Pool builder marks component materials as splittable.

### Database Integration Tests

File:

- `backend/tests/test_simulation_database.py`

Covered cases:

- Isolated SQLite test database setup.
- FGPN/BOM data seeded from `MBOM_08_08_2025-02.xlsx`.
- BOM persistence.
- PO and PO line persistence.
- Stock unit insertion.
- Feasible simulation.
- Shortfall simulation.
- Stock management WIP/in-transit material detail.
- Saved simulation does not create a launch.
- Launching a saved simulation splits component stock.
- Production handover moves issued child stock to `PRODUCTION`.

### PO Parser Compatibility Test

File:

- `backend/tests/test_po_parser_simulation_compatibility.py`

Covered cases:

- Validates parsed PO JSON shape from:
  - `2301438886.json`
- Confirms expected parsed PO fields:
  - `po_number`
  - `version`
  - `order_date`
  - `change_date`
  - `supplier`
  - `buyer`
  - `currency`
  - `stated_total`
  - `computed_total`
  - `totals_match`
  - `line_count`
  - `lines`
- Confirms line-level fields:
  - `line_no`
  - `plant`
  - `due_date`
  - `material_group`
  - `part_number`
  - `description`
  - `customer_part_ref`
  - `item_category`
  - `quantity`
  - `unit_price`
  - `total`

PO parser mapping for future ingestion:

- `po_number` -> `PurchaseOrder.po_number`
- `version` -> `PurchaseOrderVersion.version_number`
- `line_no` -> `PurchaseOrderLine.line_number`
- `part_number` -> FGPN resolver input
- `quantity` -> `PurchaseOrderLine.ordered_quantity`
- `unit_price` -> `PurchaseOrderLine.unit_price`
- `due_date` -> `PurchaseOrderLine.delivery_date`

Compatibility finding:

- Parsed PO part numbers vs MBOM FGPN codes had `0/27` exact matches.
- Normalized matching by base suffix gave `9/27` matches.
- Remaining `18/27` are mostly `741...` part numbers not present in the MBOM workbook.

This means PO ingestion should not guess the FGPN. It needs an explicit resolver/mapping strategy.

## 11. Verification Run

The focused simulation and stock tests passed:

```bash
DEBUG=false UV_CACHE_DIR=/tmp/uv-cache uv run pytest \
  tests/test_po_parser_simulation_compatibility.py \
  tests/test_simulation_allocator.py \
  tests/test_simulation_demand.py \
  tests/test_simulation_database.py
```

Result:

```text
21 passed
```

Note:

- A previous full `uv run pytest` attempt hung around `test_health.py`.
- The focused simulation/stock/PO compatibility tests passed.
- The full backend test suite still needs a separate investigation before claiming global green status.

## 12. Open Decisions And Suggested Next Steps

Recommended next decisions:

- Implement real PO ingestion from parsed PO JSON into `PurchaseOrder`, `PurchaseOrderVersion`, and `PurchaseOrderLine`.
- Define the FGPN resolver for PO `part_number`.
- Decide whether suffix normalization such as `-AF`/`-AE` to MBOM `-000` is valid business logic.
- Add a manual mapping table for PO part numbers that do not exist directly in MBOM.
- Decide whether launch is allowed to consume `IN_TRANSIT` stock, or whether in-transit should be preview-only until received.
- Add meeting approval state to saved simulations before allowing launch.
- Add upload/link fields for draft simulation document and approved meeting document.
- Implement the launch approval/create flow that inserts a `Launch` row linked to the saved simulation through `Launch.simulation_id`.
- Replace system/default user assumptions with the authenticated launch engineer and warehouse team leader.
- Consider a stronger optimizer for very large roll pools. The current exact search is used up to 18 slots, then greedy fallback is used.
