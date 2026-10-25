// Domain types derived from the SRS (Launch PO, Material Planning, Stock,
// Delivery and Finance Follow-Up System, v2.0).

export type RoleId = "R01" | "R02" | "R03" | "R04" | "R05" | "R07";

export interface Role {
  id: RoleId;
  code: string;
  name: string;
}

export interface User {
  id: string;
  fullName: string;
  username: string;
  role: RoleId;
  active: boolean;
  locked?: boolean;
  projectIds: string[];
  lastLogin?: string;
}

export interface Project {
  id: string;
  code: string;
  name: string;
  customer: string; // JIT Customer
  oemCustomer?: string; // OEM / ORM Customer
  contactName?: string;
  contactEmail?: string;
  contactPhone?: string;
  carModel?: string;
  responsibleUserIds: string[];
  status: "Active" | "On Hold" | "Closed";
  createdAt: string;
}

export type PoStatus = "Unplanned" | "In Progress" | "Done" | "Packaged" | "Delivered";

export type FieldValidation = "Validated" | "Mismatch" | "Missing" | "Not Applicable";

export interface PoLine {
  id: string;
  item: string;
  fgpn: string;
  description?: string;
  developmentLevel?: string;
  colorCode?: string;
  trimCode?: string;
  quantity: number;
  deliveredQuantity: number;
  unitPrice: number;
  expectedUnitPrice?: number;
}

export interface PoVersion {
  version: number;
  storedAt: string;
  storedBy: string;
  fileName: string;
  fields: Record<string, string | number | null>;
}

export interface PurchaseOrder {
  id: string;
  poNumber: string;
  projectId: string;
  jitCustomer: string;
  ormCustomer?: string; // ORM / OEM Customer
  contactName: string;
  contactEmail?: string;
  contactPhone?: string;
  documentDate: string;
  deliveryDate: string;
  deliveryWeek: string;
  pickUpDate?: string;
  pickUpWeek?: string;
  carModel?: string;
  engineeringPhaseLevel?: string;
  purchaseOrderLevel?: string;
  reason: string;
  status: PoStatus;
  currentVersion: number;
  lines: PoLine[];
  versions: PoVersion[];
  statusHistory: StatusEvent[];
  sourceFile: string;
}

export interface StatusEvent {
  from: PoStatus | null;
  to: PoStatus;
  at: string;
  by: string;
  reason?: string;
}

export interface ExtractedField {
  key: string;
  label: string;
  extracted: string | null;
  value: string | null;
  expected?: string | null;
  mandatory: boolean;
  status: FieldValidation;
  correctedByUser?: boolean;
}

export interface PoIntakeDraft {
  id: string;
  fileName: string;
  projectId: string;
  uploadedAt: string;
  uploadedBy: string;
  fields: ExtractedField[];
  lines: PoLine[];
}

export type MaterialType = "Roll" | "Component" | "Thread";

export interface Material {
  id: string;
  partNumber: string;
  description: string;
  type: MaterialType;
  unit: "m" | "pcs";
  status: "Active" | "Inactive";
  practicalStock: number;
  transitStock: number;
  wipStock: number;
  criticalThreshold: number;
  unitPrice: number;
}

export interface BomLine {
  id: string;
  fgpn: string;
  materialPartNumber: string;
  usageQty: number;
}

export interface BomVersion {
  id: string;
  projectId: string;
  version: number;
  fileName: string;
  uploadedAt: string;
  uploadedBy: string;
  active: boolean;
  lines: BomLine[];
}

export type MovementType =
  | "Reception"
  | "Correction"
  | "CutMan Import"
  | "Manual WIP Transfer"
  | "Transit Entry"
  | "Warehouse Issue";

export interface StockMovement {
  id: string;
  at: string;
  by: string;
  materialPartNumber: string;
  type: MovementType;
  quantity: number;
  resultingPractical: number;
  note?: string;
  originalValue?: number;
  correctedValue?: number;
  reason?: string;
}

export interface ReceptionEntry {
  id: string;
  materialPartNumber: string;
  rollSize: number;
  rollCount: number;
  totalQty: number;
  receivedAt: string;
  receivedBy: string;
  supplierRef?: string;
}

export interface TransitEntry {
  id: string;
  materialPartNumber: string;
  quantity: number;
  expectedArrival: string;
  enteredBy: string;
  enteredAt: string;
  supplierRef?: string;
}

export interface CutManImport {
  id: string;
  fileName: string;
  format: "xlsx" | "sql";
  importedAt: string;
  importedBy: string;
  sessionRef: string;
  totalSpreadingUsage: number;
  materialsUpdated: number;
  lines: { materialPartNumber: string; remainingWip: number; lastStatus: string }[];
}

export type SimulationMode = "Order + Manual Entry";
export type Feasibility = "Fully feasible" | "Partially feasible" | "Not feasible";

export interface SimulationRequirement {
  materialPartNumber: string;
  description: string;
  unit: "m" | "pcs";
  bomUsage: number;
  requiredQty: number;
  practicalStock: number;
  wipAvailable: number;
  plannedIncoming: number;
  shortfall: number;
}

export interface Simulation {
  id: string;
  ref: string;
  projectId: string;
  mode: SimulationMode;
  poIds: string[];
  runAt: string;
  runBy: string;
  bomVersionId: string;
  safetyCoefficient: number;
  targetDate?: string;
  includeFutureStock: boolean;
  feasibility: Feasibility;
  maxLaunchableQty?: number;
  requirements: SimulationRequirement[];
  meetingMinutesDocId?: string;
  approved: boolean;
  approvedAt?: string;
  approvedBy?: string;
}

export type DeliveryInstructionStatus =
  | "Code issued"
  | "Code used"
  | "Document generated"
  | "Awaiting validation"
  | "Validated"
  | "Code expired";

export interface DeliveryInstructionItem {
  materialPartNumber: string;
  description: string;
  rollSize?: number;
  quantity: number;
  unit: "m" | "pcs";
}

export interface DeliveryInstruction {
  id: string;
  ref: string;
  projectId: string;
  simulationId: string;
  createdAt: string;
  createdBy: string;
  requiredAt: string;
  code: string;
  codeExpiresAt: string;
  codeUsed: boolean;
  status: DeliveryInstructionStatus;
  receiverName?: string;
  warehouseTeamLeader?: string;
  signedDocId?: string;
  validatedAt?: string;
  validatedBy?: string;
  items: DeliveryInstructionItem[];
}

export type CustomerDeliveryStatus = "Planned" | "Pending confirmation" | "Delivered";

export interface CustomerDelivery {
  id: string;
  ref: string;
  projectId: string;
  poId: string;
  fgpn: string;
  description: string;
  quantity: number;
  unitPrice: number;
  deliveryMethod: string;
  transportCost: number;
  deliveryDate: string;
  deliveryWeek: string;
  status: CustomerDeliveryStatus;
  confirmation?: { date: string; method: string; person: string };
  invoiceDocId?: string;
}

export type DocumentType =
  | "Purchase Order PDF"
  | "BOM Excel"
  | "CutMan Report"
  | "Meeting Minutes (PV)"
  | "Simulation Draft"
  | "Warehouse Delivery Document"
  | "Signed Reception Document"
  | "Customer Delivery Instruction"
  | "Invoice";

export interface ErpDocument {
  id: string;
  type: DocumentType;
  fileName: string;
  version: number;
  uploadedAt: string;
  uploadedBy: string;
  projectId: string;
  linkedEntity: { kind: string; ref: string; id: string };
  sizeKb: number;
  draft?: boolean;
}

export interface PriceRecord {
  id: string;
  scope: "FGPN" | "Material";
  partNumber: string;
  description: string;
  trimStyle?: string;
  unitPrice: number;
  previousPrice?: number;
  effectiveDate: string;
  changedBy: string;
}

export interface ForecastPeriod {
  period: string;
  forecast: number;
  actual: number;
}

export interface AuditEvent {
  id: string;
  at: string;
  by: string;
  projectId?: string;
  category:
    | "Stock"
    | "Purchase Order"
    | "Simulation"
    | "Launch decision"
    | "Delivery"
    | "Document"
    | "Price"
    | "BOM"
    | "CutMan"
    | "Access";
  event: string;
  detail: string;
}

export interface ReferenceEntry {
  id: string;
  list: ReferenceListId;
  value: string;
  detail?: string;
  active: boolean;
  linkedRecords: number;
}

export type ReferenceListId =
  | "JIT Customers"
  | "ORM Customers"
  | "Contact Names"
  | "Finished Goods Part Numbers"
  | "Manufacturing Receivers"
  | "Delivery Methods"
  | "Material Types"
  | "Suppliers";
