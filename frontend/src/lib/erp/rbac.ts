import type { RoleId } from "./types";

/**
 * Capability map derived from the SRS role-permission matrix (section 3.2) and
 * the per-module "Role Access" tables. Capabilities are the single source of
 * truth for navigation, route guards and action rendering.
 */
export type Capability =
  | "dashboard.all"
  | "dashboard.own"
  | "project.view"
  | "project.write"
  | "po.view"
  | "po.write"
  | "po.compare"
  | "po.delete"
  | "po.status.write"
  | "bom.view"
  | "bom.write"
  | "simulation.run"
  | "simulation.view"
  | "stock.monitor"
  | "stock.search"
  | "stock.reception.write"
  | "stock.correct24h"
  | "stock.correctLocked"
  | "stock.wip.manual"
  | "stock.cutman.import"
  | "stock.transit.write"
  | "stock.threshold.write"
  | "stock.history.view"
  | "supplier.order.write"
  | "supplier.arrival.enter"
  | "supplier.arrival.confirm"
  | "handover.instruction.create"
  | "handover.code.access"
  | "handover.document.generate"
  | "handover.signed.upload"
  | "handover.validate"
  | "customer.delivery.view"
  | "customer.delivery.write"
  | "finance.view"
  | "finance.write"
  | "documents.view"
  | "audit.view"
  | "admin.users"
  | "admin.reference"
  | "system.info";

const CAPS: Record<RoleId, Capability[]> = {
  // R01 Plant Manager — read-only monitoring across all projects, audit trail.
  R01: [
    "dashboard.all",
    "project.view",
    "po.view",
    "stock.monitor",
    "stock.search",
    "stock.history.view",
    "customer.delivery.view",
    "finance.view",
    "documents.view",
    "audit.view",
    "system.info",
  ],
  // R02 Launch Manager — read all, write on assigned projects.
  R02: [
    "dashboard.all",
    "dashboard.own",
    "project.view",
    "project.write",
    "po.view",
    "po.write",
    "po.compare",
    "po.delete",
    "po.status.write",
    "bom.view",
    "bom.write",
    "simulation.run",
    "simulation.view",
    "stock.monitor",
    "stock.search",
    "stock.correctLocked",
    "stock.cutman.import",
    "stock.transit.write",
    "stock.threshold.write",
    "stock.history.view",
    "supplier.order.write",
    "handover.instruction.create",
    "handover.validate",
    "customer.delivery.view",
    "customer.delivery.write",
    "finance.view",
    "finance.write",
    "documents.view",
    "audit.view",
    "system.info",
  ],
  // R03 Launch Engineer — assigned projects only.
  R03: [
    "dashboard.own",
    "project.view",
    "project.write",
    "po.view",
    "po.write",
    "po.compare",
    "po.delete",
    "po.status.write",
    "bom.view",
    "bom.write",
    "simulation.run",
    "simulation.view",
    "stock.monitor",
    "stock.search",
    "stock.correctLocked",
    "stock.cutman.import",
    "stock.transit.write",
    "stock.threshold.write",
    "stock.history.view",
    "supplier.order.write",
    "handover.instruction.create",
    "handover.validate",
    "customer.delivery.view",
    "customer.delivery.write",
    "finance.view",
    "finance.write",
    "documents.view",
    "audit.view",
    "system.info",
  ],
  // R04 Warehouse Team Leader — reception + code-authorised handover.
  R04: [
    "stock.monitor",
    "stock.search",
    "stock.reception.write",
    "stock.correct24h",
    "stock.wip.manual",
    "stock.history.view",
    "supplier.arrival.confirm",
    "handover.code.access",
    "handover.document.generate",
    "handover.signed.upload",
    "system.info",
  ],
  // R05 Warehouse Personnel — reception entry only.
  R05: ["stock.search", "stock.reception.write", "supplier.arrival.enter", "system.info"],
  // R07 System Administrator — no business data.
  R07: ["admin.users", "admin.reference", "audit.view", "system.info"],
};

export function can(role: RoleId, cap: Capability): boolean {
  return CAPS[role].includes(cap);
}

export function canAny(role: RoleId, caps: Capability[]): boolean {
  return caps.some((c) => can(role, c));
}

/** Projects a role may see: R01/R02 see all, R03 assigned only, others none. */
export function visibleProjectIds(role: RoleId, assigned: string[], allIds: string[]): string[] {
  if (role === "R01" || role === "R02") return allIds;
  if (role === "R03") return assigned;
  return [];
}

/** Write access is always limited to assigned projects (SRS 3.2 "Write (own)"). */
export function canWriteProject(role: RoleId, assigned: string[], projectId: string): boolean {
  if (role !== "R02" && role !== "R03") return false;
  return assigned.includes(projectId);
}
