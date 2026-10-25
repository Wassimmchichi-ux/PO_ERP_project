import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { PageHeader } from "@/components/erp/PageHeader";
import { DataTable, type Column } from "@/components/erp/DataTable";
import { StatusBadge } from "@/components/erp/StatusBadge";
import { AccessDenied } from "@/components/erp/EmptyState";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSession } from "@/lib/erp/session";
import {
  fetchStockHistory,
  stockHistoryQueryKey,
  type StockMovementItem,
} from "@/lib/erp/stockApi";
import { readApiError } from "@/lib/erp/api";
import { fmtDateTime, nf } from "@/lib/erp/format";
import { pageTitle } from "@/lib/erp/appInfo";

export const Route = createFileRoute("/stock/history")({
  head: () => ({ meta: [{ title: pageTitle("Stock Movement History") }] }),
  component: StockHistoryPage,
});

const LABELS: Record<string, string> = {
  TRANSIT_DECLARED: "Transit declared",
  TRANSIT_UPDATED: "Transit updated",
  TRANSIT_CANCELLED: "Transit cancelled",
  ETA_CHANGED: "ETA changed",
  ARRIVAL_ENTERED: "Receipt entered",
  SUPPLIER_RECEIPT_CONFIRMED: "Supplier receipt confirmed",
  WAREHOUSE_RECEPTION: "Warehouse reception",
  RECEPTION_CORRECTED: "Reception corrected",
  STOCK_ISSUED_TO_PRODUCTION: "Issued to production",
  PRODUCTION_RECEIVED: "Production received",
  CUTMAN_CONSUMPTION: "CutMan consumption",
  WAREHOUSE_BASELINE: "Existing warehouse stock",
  TRANSIT_BASELINE: "Existing transit stock",
  PRODUCTION_BASELINE: "Existing production stock",
  ISSUED_BASELINE: "Existing issued stock",
};

const movementTone = (type: string): "ok" | "warn" | "info" | "accent" | "neutral" | "danger" => {
  if (["WAREHOUSE_RECEPTION", "SUPPLIER_RECEIPT_CONFIRMED", "PRODUCTION_RECEIVED"].includes(type))
    return "ok";
  if (["TRANSIT_DECLARED", "TRANSIT_UPDATED", "ETA_CHANGED"].includes(type)) return "accent";
  if (["RECEPTION_CORRECTED", "TRANSIT_CANCELLED"].includes(type)) return "warn";
  if (type === "CUTMAN_CONSUMPTION") return "info";
  return "neutral";
};

const movementLabel = (type: string) => LABELS[type] ?? type.replaceAll("_", " ").toLowerCase();

function StockHistoryPage() {
  const { can } = useSession();
  const [type, setType] = useState("all");
  const [pn, setPn] = useState("all");
  const history = useQuery({
    queryKey: stockHistoryQueryKey,
    queryFn: ({ signal }) => fetchStockHistory(signal),
  });

  if (!can("stock.history.view")) return <AccessDenied what="the stock movement history" />;

  const allRows = history.data?.items ?? [];
  const rows = allRows
    .filter((movement) => type === "all" || movement.movement_type === type)
    .filter((movement) => pn === "all" || movement.material_part_number === pn);
  const types = [...new Set(allRows.map((movement) => movement.movement_type))].sort();
  const materials = [...new Set(allRows.map((movement) => movement.material_part_number))].sort();
  const columns: Column<StockMovementItem>[] = [
    {
      key: "at",
      header: "Date / time",
      mono: true,
      cell: (m) => fmtDateTime(m.occurred_at),
      sortValue: (m) => m.occurred_at,
    },
    { key: "by", header: "By", cell: (m) => m.actor_name },
    {
      key: "material",
      header: "Material",
      mono: true,
      cell: (m) => (
        <span>
          <span className="font-medium">{m.material_part_number}</span>
          <span className="ml-2 text-xs text-muted-foreground">{m.material_description}</span>
        </span>
      ),
      sortValue: (m) => m.material_part_number,
    },
    {
      key: "type",
      header: "Movement",
      cell: (m) => (
        <StatusBadge tone={movementTone(m.movement_type)}>
          {movementLabel(m.movement_type)}
        </StatusBadge>
      ),
      sortValue: (m) => m.movement_type,
    },
    {
      key: "qty",
      header: "Quantity",
      align: "right",
      mono: true,
      cell: (m) => {
        const value = Number(m.quantity_change);
        return (
          <span
            className={value < 0 ? "text-danger" : value > 0 ? "text-ok" : "text-muted-foreground"}
          >
            {value > 0 ? "+" : ""}
            {nf.format(value)} {m.unit}
          </span>
        );
      },
      sortValue: (m) => Number(m.quantity_change),
    },
    {
      key: "result",
      header: "Warehouse after",
      align: "right",
      mono: true,
      cell: (m) =>
        m.warehouse_quantity_after == null
          ? "—"
          : `${nf.format(Number(m.warehouse_quantity_after))} ${m.unit}`,
      sortValue: (m) => Number(m.warehouse_quantity_after ?? 0),
    },
    {
      key: "unit",
      header: "Stock unit / source",
      cell: (m) => (
        <div className="text-xs">
          <div className="num text-foreground">
            {m.stock_unit_reference ?? (m.stock_unit_id ? `SU-${m.stock_unit_id}` : "—")}
          </div>
          {m.supplier_name && <div className="text-muted-foreground">{m.supplier_name}</div>}
          {m.source_reference && (
            <div className="text-muted-foreground">Ref. {m.source_reference}</div>
          )}
        </div>
      ),
    },
    {
      key: "detail",
      header: "Detail",
      cell: (m) => (
        <div className="max-w-md text-xs text-muted-foreground">
          {m.from_status && m.to_status && (
            <div className="num text-foreground">
              {m.from_status} → {m.to_status}
            </div>
          )}
          {m.reason && <div className="text-warn">Reason: {m.reason}</div>}
          {m.note && <div>{m.note}</div>}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Stock movement history"
        subtitle="One immutable database ledger connects supplier transit, warehouse reception, launch issue, production handover and CutMan consumption."
        crumbs={[{ label: "Stock", to: "/stock" }, { label: "History" }]}
      />
      <div className="p-4">
        <div className="panel overflow-hidden">
          <DataTable
            rows={rows}
            columns={columns}
            rowKey={(movement) => String(movement.movement_id)}
            searchable={(m) =>
              `${m.material_part_number} ${m.material_description} ${movementLabel(m.movement_type)} ${m.actor_name} ${m.note ?? ""} ${m.reason ?? ""} ${m.source_reference ?? ""}`
            }
            searchPlaceholder="Search material, author or supplier reference…"
            rowTone={(m) =>
              ["RECEPTION_CORRECTED", "TRANSIT_CANCELLED"].includes(m.movement_type)
                ? "warn"
                : undefined
            }
            toolbar={
              <div className="flex gap-2">
                <Select value={type} onValueChange={setType}>
                  <SelectTrigger className="h-8 w-52 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All movement types</SelectItem>
                    {types.map((value) => (
                      <SelectItem key={value} value={value}>
                        {movementLabel(value)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={pn} onValueChange={setPn}>
                  <SelectTrigger className="h-8 w-56 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All materials</SelectItem>
                    {materials.map((value) => (
                      <SelectItem key={value} value={value}>
                        {value}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            }
            emptyTitle={
              history.isLoading
                ? "Loading movement history…"
                : history.isError
                  ? "Could not load movement history"
                  : "No movement matches the filters"
            }
            {...(history.isError
              ? {
                  emptyDescription: readApiError(
                    history.error,
                    "The stock history API is unavailable.",
                  ),
                }
              : {})}
          />
        </div>
      </div>
    </>
  );
}
