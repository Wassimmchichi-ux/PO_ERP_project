import { apiFetch, throwApiError } from "./api";

export interface StockSummaryItem {
  material_part_number: string;
  description: string;
  material_type: string;
  unit: string;
  critical_threshold: string;
  unit_price: string;
  warehouse_quantity: string;
  production_quantity: string;
  in_transit_quantity: string;
  total_available_quantity: string;
  status: string;
}

export interface StockMovementItem {
  movement_id: number;
  occurred_at: string;
  actor_user_id: string;
  actor_name: string;
  material_part_number: string;
  material_description: string;
  unit: string;
  movement_type: string;
  quantity_change: string;
  warehouse_quantity_after?: string | null;
  stock_unit_id?: number | null;
  stock_unit_reference?: string | null;
  supplier_order_id?: number | null;
  supplier_name?: string | null;
  source_reference?: string | null;
  from_status?: string | null;
  to_status?: string | null;
  reason?: string | null;
  note?: string | null;
}

export const stockSummaryQueryKey = ["stock-summary"] as const;
export const stockHistoryQueryKey = ["stock-history"] as const;

export async function fetchStockSummary(signal?: AbortSignal) {
  const response = await apiFetch("/stock/summary", signal ? { signal } : {});
  if (!response.ok) await throwApiError(response);
  return (await response.json()) as { items: StockSummaryItem[]; total: number };
}

export async function fetchStockHistory(signal?: AbortSignal) {
  const response = await apiFetch("/stock/history", signal ? { signal } : {});
  if (!response.ok) await throwApiError(response);
  return (await response.json()) as { items: StockMovementItem[]; total: number };
}

export function materialCategory(materialType: string, unit: string) {
  const value = materialType.trim().toUpperCase();
  if (value.includes("THREAD")) return "Thread";
  if (value === "M" || unit.trim().toLowerCase() === "m") return "Roll";
  return "Component";
}
