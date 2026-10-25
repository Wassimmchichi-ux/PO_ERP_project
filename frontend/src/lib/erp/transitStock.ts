import { useQuery } from "@tanstack/react-query";
import { apiFetch, throwApiError } from "./api";

export interface InTransitStock {
  stock_unit_id: number;
  stock_unit_reference: string | null;
  material_part_number: string;
  description: string;
  unit: string;
  quantity: string | number;
  expected_quantity: string | number;
  actual_quantity: string | number | null;
  quantity_difference: string | number | null;
  compatible: boolean | null;
  expected_arrival_date: string | null;
  days_until_arrival: number | null;
  status: "ON_TIME" | "DELAYED";
  workflow_status: string;
  assigned_user_name: string | null;
  supplier_order_id: number | null;
  supplier_order_line_id: number | null;
  stock_unit_kind: "ROLL" | "COMPONENT" | null;
  supplier_name: string | null;
  supplier_reference: string | null;
  supplier_order_status: string | null;
  project_id: number | null;
  project_code: string | null;
  project_name: string | null;
  arrival_entered_by_name: string | null;
  arrival_entered_at: string | null;
}

export const transitStockQueryKey = ["stock", "in-transit"] as const;

export function useTransitStock(enabled = true) {
  return useQuery({
    queryKey: transitStockQueryKey,
    enabled,
    queryFn: async ({ signal }): Promise<InTransitStock[]> => {
      const response = await apiFetch("/stock/in-transit", { signal });
      if (!response.ok) await throwApiError(response);
      const payload: { items: InTransitStock[] } = await response.json();
      return payload.items;
    },
  });
}

export async function updateArrivalDate(stockUnitId: number, date: string, reason: string) {
  const response = await apiFetch(`/stock/units/${stockUnitId}/expected-arrival`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected_arrival_date: date, reason }),
  });
  if (!response.ok) await throwApiError(response);
  return response.json() as Promise<InTransitStock>;
}
