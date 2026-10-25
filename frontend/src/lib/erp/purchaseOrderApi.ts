import { apiFetch, throwApiError } from "./api";

export interface PurchaseOrderListItem {
  po_id: number;
  po_number: string;
  project_id: number | null;
  project_code: string | null;
  project_name: string | null;
  jit_customer: string;
  oem_customer: string | null;
  contact_name: string;
  current_version: number | null;
  status: string;
  fgpn_codes: string[];
  ordered_quantity: string;
  delivered_quantity: string;
  remaining_quantity: string;
  open_amount: string;
  delivery_date: string | null;
  delivery_week: string | null;
  updated_at: string;
}

export interface PurchaseOrderListResponse {
  items: PurchaseOrderListItem[];
  total: number;
}

export interface PurchaseOrderLineDetail {
  po_line_id: number;
  item_number: string | null;
  fgpn_code: string;
  description: string | null;
  ordered_quantity: string;
  delivered_quantity: string;
  remaining_quantity: string;
  unit_price: string;
  open_amount: string;
  delivery_date: string | null;
}

export interface PurchaseOrderVersionDetail {
  po_version_id: number;
  version_number: number;
  document_date: string | null;
  source_file_name: string;
  created_at: string;
  created_by_name: string;
  change_reason: string | null;
  is_current: boolean;
}

export interface PurchaseOrderDetail extends PurchaseOrderListItem {
  contact_email: string | null;
  contact_phone: string | null;
  document_date: string | null;
  car_model: string | null;
  engineering_phase_level: string | null;
  purchase_order_level: string | null;
  reason: string | null;
  source_file_name: string | null;
  lines: PurchaseOrderLineDetail[];
  versions: PurchaseOrderVersionDetail[];
}

export const purchaseOrdersQueryKey = ["purchase-orders"] as const;

export async function fetchPurchaseOrders(
  signal?: AbortSignal,
): Promise<PurchaseOrderListResponse> {
  const response = await apiFetch("/purchase-orders", signal ? { signal } : {});
  if (!response.ok) await throwApiError(response);
  return (await response.json()) as PurchaseOrderListResponse;
}

export async function fetchPurchaseOrder(
  poId: string | number,
  signal?: AbortSignal,
): Promise<PurchaseOrderDetail> {
  const response = await apiFetch(`/purchase-orders/${poId}`, signal ? { signal } : {});
  if (!response.ok) await throwApiError(response);
  return (await response.json()) as PurchaseOrderDetail;
}

export async function deletePurchaseOrder(
  poId: string | number,
  deletionReason: string,
): Promise<void> {
  const response = await apiFetch(`/purchase-orders/${poId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ deletion_reason: deletionReason }),
  });
  if (!response.ok) await throwApiError(response);
}

export interface VersionComparisonRow {
  field: string;
  a: string | null;
  b: string | null;
  status: "Unchanged" | "Changed" | "Added" | "Removed";
}

export interface VersionComparisonResponse {
  po_id: number;
  po_number: string;
  version_a: number;
  version_b: number;
  rows: VersionComparisonRow[];
}

export async function fetchPoComparison(
  poId: string | number,
  v1: string | number,
  v2: string | number,
  signal?: AbortSignal,
): Promise<VersionComparisonResponse> {
  const response = await apiFetch(`/purchase-orders/${poId}/compare?v1=${v1}&v2=${v2}`, signal ? { signal } : {});
  if (!response.ok) await throwApiError(response);
  return (await response.json()) as VersionComparisonResponse;
}
