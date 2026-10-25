import type { RoleId } from "./types";

export type BackendRole =
  | "ADMIN"
  | "PLANT_MANAGER"
  | "LAUNCH_MANAGER"
  | "LAUNCH_ENGINEER"
  | "WAREHOUSE_TEAM_LEADER"
  | "WAREHOUSE_Personnel"
  | "MANUFACTURING_OPERATOR";

const FRONTEND_TO_BACKEND_ROLE: Record<RoleId, BackendRole> = {
  R01: "PLANT_MANAGER",
  R02: "LAUNCH_MANAGER",
  R03: "LAUNCH_ENGINEER",
  R04: "WAREHOUSE_TEAM_LEADER",
  R05: "WAREHOUSE_Personnel",
  R07: "ADMIN",
};

const BACKEND_TO_FRONTEND_ROLE: Record<string, RoleId> = {
  ADMIN: "R07",
  PLANT_MANAGER: "R01",
  LAUNCH_MANAGER: "R02",
  LAUNCH_ENGINEER: "R03",
  WAREHOUSE_TEAM_LEADER: "R04",
  WAREHOUSE_Personnel: "R05",
  MANUFACTURING_OPERATOR: "R05",
};

export function toBackendRole(role: RoleId): BackendRole {
  return FRONTEND_TO_BACKEND_ROLE[role];
}

export function toRoleId(role: string): RoleId {
  return BACKEND_TO_FRONTEND_ROLE[role] ?? "R03";
}
