# End-To-End Launch PO Workflow Documentation

This document explains the complete workflow from receiving a parsed PO JSON file until launching production and confirming material handover.

## 1. Parsed PO File Is Produced

An external parser, provided by the colleague, reads the original PO document and produces a structured JSON file.

Example file:

```text
2301416000.json
```

The parsed JSON contains:

- PO header values, such as `po_number`, `version`, `order_date`, supplier/customer contact values, totals.
- PO line values, such as `line_no`, `part_number`, `quantity`, `unit_price`, `total`, `due_date`.

At this moment, the data is not trusted yet. It is parser output, not final business data.

## 2. Upload Parsed PO JSON

The system stores the parsed JSON in a staging table.

Endpoint:

```http
POST /purchase-orders/parsed/upload-json
```

Table used:

```text
ParsedPurchaseOrder
```

Purpose of `ParsedPurchaseOrder`:

- Store the full original parser output in `parsed_payload`.
- Keep parser metadata such as `source_file_name`, `parser_name`, `parser_version`.
- Track review/import status:
  - `PARSED`
  - `CORRECTED`
  - `VALIDATED`
  - `IMPORTED`
  - `REJECTED`
- Link later to the real imported `PurchaseOrder` through `validated_po_id`.

Nothing is inserted yet into:

- `PurchaseOrder`
- `PurchaseOrderVersion`
- `PurchaseOrderLine`
- `FGPN`

## 3. Launch Engineer Reviews Parsed Values

The frontend loads the parsed PO review screen.

Endpoint:

```http
GET /purchase-orders/parsed/{parsed_po_id}
```

The response contains:

- `parsed_payload`: original parser output.
- `corrections`: saved correction diffs.
- `effective_payload`: original parsed payload with confirmed corrections applied.

The UI should show the parsed values and allow the launch engineer to correct wrong fields.

## 4. Launch Engineer Saves Corrections

The frontend sends only changed fields, not the full PO payload.

Endpoint:

```http
PUT /purchase-orders/parsed/{parsed_po_id}/corrections
```

Table used:

```text
ParsedPurchaseOrderCorrection
```

Example correction:

```json
{
  "corrections": [
    {
      "field_path": "lines[0].quantity",
      "corrected_value": 22
    }
  ]
}
```

Correction record stores:

- `parsed_po_id`
- `field_path`
- `original_value`
- `corrected_value`
- `confirmed`
- `corrected_by`
- `corrected_at`

Important:

- The original `parsed_payload` is not overwritten.
- Corrections are stored separately for traceability.
- `lines[0]` means first item in the JSON array, not PO line number `00001`.
- After corrections are saved, validation is automatically run inside the service.
- If validation passes, `ParsedPurchaseOrder.status` becomes `VALIDATED`.
- If validation fails, `ParsedPurchaseOrder.status` stays `CORRECTED`.

## 5. Validate Corrected PO

The explicit validation endpoint can still be called to recheck the current effective payload.

Endpoint:

```http
POST /purchase-orders/parsed/{parsed_po_id}/validate
```

Validation checks include:

- Required header fields exist.
- PO has at least one line.
- Required line fields exist.
- Quantities are valid.
- Unit prices are valid.
- Line totals are valid.
- `line_count` matches actual line count.
- Header totals are consistent with line totals.

If valid, `ParsedPurchaseOrder.status` becomes:

```text
VALIDATED
```

The data is now ready to become real business data.

## 6. Import Corrected PO Into Real Tables

After validation, the system imports the effective corrected payload.

Endpoint:

```http
POST /purchase-orders/parsed/{parsed_po_id}/import
```

Request body requires context that is not inside the parsed JSON:

```json
{
  "project_id": 1,
  "customer_id": 1,
  "contact_id": 1,
  "delivery_method_id": 1,
  "change_reason": "Imported from corrected parsed PO"
}
```

Tables written:

- `PurchaseOrder`
- `PurchaseOrderVersion`
- `PurchaseOrderLine`
- `FGPN`
- `FGPNPriceHistory`, only when price changed
- `ParsedPurchaseOrder`

## 7. PurchaseOrder Creation Or Update

The system checks if the PO already exists by:

```text
po_number
```

If no PO exists:

- Create a new `PurchaseOrder`.
- Set status to `Unplanned`.
- Temporarily leave `current_version_id` empty during creation.
- Create the PO version.
- Update `PurchaseOrder.current_version_id` to the created version.

If PO already exists:

- Reuse the existing `PurchaseOrder`.
- Create a new `PurchaseOrderVersion`.
- Update `current_version_id` to the new version.

Duplicate version protection:

- The same `po_id + version_number` cannot be imported twice.

## 8. PurchaseOrderVersion Creation

One imported JSON creates one PO version.

Table:

```text
PurchaseOrderVersion
```

Fields come from:

- `version` -> `version_number`
- `order_date` -> `document_date`
- `document_id` or generated PO document -> `document_id`
- current user/system user -> `created_by`
- import request -> `change_reason`

## 9. FGPN Resolution And Creation

Each PO line has:

```text
part_number
```

The system resolves the FGPN catalog item by:

```text
project_id + part_number
```

Project catalog rule:

```text
FGPN(project_id, fgpn_code) is unique
```

PO relationship rule:

```text
PurchaseOrderLine links one PO version to one FGPN
```

This makes PO and FGPN many-to-many inside a project:

- One PO version can contain many FGPNs.
- One FGPN can appear in many POs.
- The selected simulation item is identified by `po_id + fgpn_id` or, more precisely, by the matching `PurchaseOrderLine`.
- The database prevents the same FGPN from appearing twice in the same PO version with `PurchaseOrderLine(po_version_id, fgpn_id)`.

If FGPN exists:

- Use existing `fgpn_id`.

If FGPN does not exist:

- Create a new `FGPN`.
- `fgpn_code = part_number`
- `project_id = selected project`
- `description = line description`
- `unit_price = line unit_price`

This means PO import can create project-specific FGPNs automatically, then connect each PO to those FGPNs through `PurchaseOrderLine`.

## 10. FGPN Price History

If an existing FGPN has a different unit price from the imported PO line:

- Update `FGPN.unit_price`.
- Insert a row in `FGPNPriceHistory`.
- Insert an audit record in `AuditLog`.

Table:

```text
FGPNPriceHistory
```

Stores:

- `fgpn_id`
- `old_price`
- `new_price`
- `effective_date`
- `changed_by`
- `audit_id`

## 11. PurchaseOrderLine Creation

For each parsed PO line, the system creates a `PurchaseOrderLine`.

Table:

```text
PurchaseOrderLine
```

Mapping:

- `line_no` -> `line_number`
- `line_no` -> `item_number`
- resolved/created FGPN -> `fgpn_id`
- `description` -> `description`
- `quantity` -> `ordered_quantity`
- `unit_price` -> `unit_price`
- `due_date` -> `delivery_date`
- import request `delivery_method_id` -> `delivery_method_id`

After import, `ParsedPurchaseOrder.status` becomes:

```text
IMPORTED
```

And:

```text
ParsedPurchaseOrder.validated_po_id = PurchaseOrder.po_id
```

## 12. BOM Upload

Before simulation can work for an FGPN, the FGPN must have a current BOM.

Endpoint:

```http
POST /boms/upload
```

Tables written:

- `Document`
- `BOM`
- `BOMLine`
- `Material`
- `MaterialType`

Important material rules:

- BOM line `part_type = M` creates/uses material type `M`, unit `sqm`.
- BOM line `part_type = S` creates/uses material type `S`, unit `pcs`.

Simulation uses:

- `total_sqm` for material type `M`.
- `total_quantity` for material type `S`.

## 13. Stock Must Exist

Simulation checks available material from stock.

Table:

```text
StockUnit
```

Relevant statuses:

- `WAREHOUSE`
- `IN_TRANSIT`
- `ISSUED_TO_PRODUCTION`
- `PRODUCTION`

When warehouse records arrival, stock can optionally be affected to a launch owner:

- `StockUnit.user_id = launch engineer/launch manager user id` means the stock is affected to that launch owner.
- `StockUnit.user_id = NULL` means global enterprise stock.

This ownership does not normally block other launch engineers from seeing or using stock in normal simulation mode. It is mainly used so the simulation result and draft meeting document can show which stock units were originally affected to which launch owner.

Simulation availability:

- `WAREHOUSE` is available.
- `IN_TRANSIT` is available only if simulation includes in-transit stock.
- `PRODUCTION` is WIP and can be used as remaining production quantity.
- `ISSUED_TO_PRODUCTION` is not available for simulation.

## 14. Preview Simulation

The launch engineer selects specific PO+FGPN rows and quantities.

Endpoint:

```http
POST /simulations/preview
```

Request contains an ordered list:

```json
{
  "project_id": 1,
  "fgpns": [
    {
      "po_id": 1,
      "fgpn_id": 1,
      "po_line_id": 1,
      "requested_quantity": "100"
    },
    {
      "po_id": 2,
      "fgpn_id": 2,
      "po_line_id": 2,
      "requested_quantity": "140"
    }
  ],
  "allocation_strategy": "PRIORITY",
  "include_in_transit": false,
  "safety_coefficient": "1.0",
  "stock_scope_mode": "ALL"
}
```

Priority:

- The order of `fgpns` is the priority.
- First row consumes available stock first.
- Second row consumes what remains.

The preview does not mutate real stock.

Stock scope modes:

- `ALL`: use all available stock, whether global or affected to a launch owner.
- `OWNED_ONLY`: use only stock affected to `stock_owner_user_id`.
- `OWNED_ONLY` with `include_global_stock = true`: use stock affected to `stock_owner_user_id` plus global stock where `StockUnit.user_id` is `NULL`.

Owned-only example:

```json
{
  "project_id": 1,
  "fgpns": [
    {
      "po_id": 1,
      "fgpn_id": 1,
      "po_line_id": 1,
      "requested_quantity": "100"
    }
  ],
  "allocation_strategy": "PRIORITY",
  "include_in_transit": false,
  "safety_coefficient": "1.0",
  "stock_scope_mode": "OWNED_ONLY",
  "stock_owner_user_id": "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb",
  "include_global_stock": true
}
```

Allocation details include:

- `assigned_user_id`
- `assigned_user_name`
- `assigned_user_role`

The draft meeting document should show those fields beside each selected stock unit.

## 15. Simulation Allocation Logic

For each selected FGPN:

1. Load current BOM.
2. Calculate required materials.
3. Build stock pools from warehouse, production WIP, and optionally in-transit.
4. Allocate by priority.
5. Calculate launchable quantity.
6. Report material usage and shortfall.

Material allocation rules:

- Roll/material `M` is whole issue.
- A roll cannot be partially sent to production.
- Component/accessory/material `S` can be partially issued.
- Production WIP can be partially consumed.

## 16. Save Simulation

If the launch engineer wants to keep the simulation result:

Endpoint:

```http
POST /simulations
```

Tables written:

- `Simulation`
- `SimulationFGPN`
- `StockAllocation`

Important:

- Saving simulation does not create `Launch`.
- Saving simulation does not mutate `StockUnit`.
- Stock allocations with type `SIMULATION` are audit/planning records only.
- `Simulation.stock_scope_mode` stores whether the simulation used `ALL` or `OWNED_ONLY`.
- `Simulation.stock_owner_user_id` stores the launch owner only for owned-only simulations.
- `Simulation.include_global_stock` stores whether global stock was allowed in an owned-only simulation.

## 17. Meeting And Approval

Business step:

1. Launch engineer exports or uploads a simulation summary/draft.
2. Team reviews it in the meeting.
3. Meeting approval document is uploaded.
4. Only after approval should the system create/confirm launch.

Current implementation note:

- The backend has launch review/launch endpoints.
- A dedicated approval workflow/document status may still need to be added depending on the final UI process.

## 18. Review Before Launch

Because there is a gap between simulation and launch, stock may change.

Endpoint:

```http
POST /simulations/{simulation_id}/launch-review
```

The system checks:

- Are the stock units used in the saved simulation still available?
- If yes, launch can proceed with original simulated stock units.
- If no, rerun allocation using current stock.
- If replacements satisfy the same saved quantities, launch can still proceed.
- If not, launch is blocked.

## 19. Launch Saved Simulation

Endpoint:

```http
POST /simulations/{simulation_id}/launch
```

Tables written:

- `StockAllocation`, with `allocation_type = LAUNCH`
- `StockUnit`, updated/split depending on material behavior

Important:

- `LAUNCH` allocation means actual issue to production.
- These stock units cannot be simulated again.
- Status becomes `ISSUED_TO_PRODUCTION`.

## 20. Stock Issue Rules

For roll/material type `M`:

- Whole roll is issued.
- Original `StockUnit` status becomes `ISSUED_TO_PRODUCTION`.
- Quantity stays unchanged for traceability.

For component/accessory/material type `S`:

- If whole package is issued, original `StockUnit` becomes `ISSUED_TO_PRODUCTION`.
- If partial package is issued:
  - Parent stock unit keeps remaining quantity.
  - Child stock unit is created with issued quantity.
  - Child status becomes `ISSUED_TO_PRODUCTION`.
  - Child points to parent through `parent_stock_unit_id`.

## 21. Production Handover

After warehouse physically gives materials to production, production engineer signs a handover document.

Endpoint:

```http
POST /stock/units/{stock_unit_id}/production-handover
```

Request:

```json
{
  "handover_document_id": 1
}
```

The system changes:

```text
ISSUED_TO_PRODUCTION -> PRODUCTION
```

And stores:

- `handover_document_id`
- `received_by_production_at`

## 22. Final State

At the end of the full workflow:

- Original PO document is stored in `Document`.
- Parser output is stored in `ParsedPurchaseOrder`.
- Corrections are stored in `ParsedPurchaseOrderCorrection`.
- Final validated PO is stored in:
  - `PurchaseOrder`
  - `PurchaseOrderVersion`
  - `PurchaseOrderLine`
- FGPNs are resolved or created in `FGPN`.
- FGPN price changes are audited in `FGPNPriceHistory`.
- BOM is stored in `BOM` and `BOMLine`.
- Optional stock ownership is stored on `StockUnit.user_id`.
- Simulation is saved in `Simulation`.
- Selected simulation rows are saved in `SimulationFGPN`.
- Planned and launch allocations are saved in `StockAllocation`.
- Issued/production stock state is tracked in `StockUnit`.

## 23. Practical Endpoint Order

Typical happy path:

```text
POST /purchase-orders/parsed/upload-json
GET  /purchase-orders/parsed/{parsed_po_id}
PUT  /purchase-orders/parsed/{parsed_po_id}/corrections
POST /purchase-orders/parsed/{parsed_po_id}/validate
POST /purchase-orders/parsed/{parsed_po_id}/import
POST /boms/upload
POST /stock/units/reception
POST /simulations/preview
POST /simulations
POST /simulations/{simulation_id}/launch-review
POST /simulations/{simulation_id}/launch
POST /stock/units/{stock_unit_id}/production-handover
```

## 24. Current Open Points

Still to decide or improve:

- Authentication should replace the temporary system user.
- Meeting approval should likely have explicit status/document workflow before launch.
- The UI should decide whether corrections are saved one by one or all together.
- Import currently treats parsed PO `part_number` as `FGPN.fgpn_code` scoped to project.
- If business needs a different part-number-to-FGPN mapping, add a resolver/mapping table before import.
- Full backend test suite still needs separate investigation because an earlier full run hung around `test_health.py`.
