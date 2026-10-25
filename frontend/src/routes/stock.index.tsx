import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { PageHeader } from "@/components/erp/PageHeader";
import { DataTable, type Column } from "@/components/erp/DataTable";
import { StatusBadge } from "@/components/erp/StatusBadge";
import { AccessDenied } from "@/components/erp/EmptyState";
import { ConfirmDialog } from "@/components/erp/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiFetch, readApiError, throwApiError } from "@/lib/erp/api";
import { useSession } from "@/lib/erp/session";
import {
  fetchStockSummary,
  materialCategory,
  stockSummaryQueryKey,
  type StockSummaryItem,
} from "@/lib/erp/stockApi";
import { nf } from "@/lib/erp/format";
import { pageTitle } from "@/lib/erp/appInfo";

export const Route = createFileRoute("/stock/")({
  head: () => ({ meta: [{ title: pageTitle("Stock Monitoring") }] }),
  component: StockPage,
});

const quantity = (value: string) => Number(value || 0);
const isCritical = (item: StockSummaryItem) =>
  quantity(item.warehouse_quantity) <= quantity(item.critical_threshold);

function StockPage() {
  const { can } = useSession();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState("all");
  const [edit, setEdit] = useState<StockSummaryItem | null>(null);
  const [threshold, setThreshold] = useState("");
  const summary = useQuery({
    queryKey: stockSummaryQueryKey,
    queryFn: ({ signal }) => fetchStockSummary(signal),
  });
  const updateThreshold = useMutation({
    mutationFn: async () => {
      if (!edit) throw new Error("Select a material first.");
      const response = await apiFetch(
        `/stock/materials/${encodeURIComponent(edit.material_part_number)}/threshold`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ critical_threshold: Number(threshold) }),
        },
      );
      if (!response.ok) await throwApiError(response);
    },
    onSuccess: async () => {
      toast.success("Critical threshold saved in the database.");
      setEdit(null);
      await queryClient.invalidateQueries({ queryKey: stockSummaryQueryKey });
    },
    onError: (error) => toast.error(readApiError(error, "Could not save the threshold.")),
  });

  if (!can("stock.monitor")) return <AccessDenied what="stock monitoring" />;

  const materials = summary.data?.items ?? [];
  const rows = materials.filter((item) => {
    if (filter === "critical") return isCritical(item);
    if (filter === "all") return true;
    return materialCategory(item.material_type, item.unit) === filter;
  });
  const columns: Column<StockSummaryItem>[] = [
    {
      key: "pn",
      header: "Part number",
      mono: true,
      cell: (m) => m.material_part_number,
      sortValue: (m) => m.material_part_number,
    },
    {
      key: "desc",
      header: "Description",
      cell: (m) => <span className="text-xs">{m.description}</span>,
    },
    {
      key: "type",
      header: "Type",
      cell: (m) => (
        <StatusBadge tone="neutral" dot={false}>
          {materialCategory(m.material_type, m.unit)}
        </StatusBadge>
      ),
    },
    {
      key: "warehouse",
      header: "Warehouse",
      align: "right",
      mono: true,
      cell: (m) => `${nf.format(quantity(m.warehouse_quantity))} ${m.unit}`,
      sortValue: (m) => quantity(m.warehouse_quantity),
    },
    {
      key: "transit",
      header: "In transit",
      align: "right",
      mono: true,
      cell: (m) => `${nf.format(quantity(m.in_transit_quantity))} ${m.unit}`,
      sortValue: (m) => quantity(m.in_transit_quantity),
    },
    {
      key: "total",
      header: "Warehouse + transit",
      align: "right",
      mono: true,
      cell: (m) => (
        <span className="font-semibold">
          {nf.format(quantity(m.warehouse_quantity) + quantity(m.in_transit_quantity))} {m.unit}
        </span>
      ),
    },
    {
      key: "wip",
      header: "Production / WIP",
      align: "right",
      mono: true,
      cell: (m) => `${nf.format(quantity(m.production_quantity))} ${m.unit}`,
    },
    {
      key: "threshold",
      header: "Critical threshold",
      align: "right",
      mono: true,
      cell: (m) => `${nf.format(quantity(m.critical_threshold))} ${m.unit}`,
    },
    {
      key: "state",
      header: "State",
      cell: (m) =>
        isCritical(m) ? (
          <StatusBadge tone="danger">Below threshold</StatusBadge>
        ) : (
          <StatusBadge tone="ok">Sufficient</StatusBadge>
        ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      cell: (m) =>
        can("stock.threshold.write") ? (
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => {
              setEdit(m);
              setThreshold(m.critical_threshold);
            }}
          >
            Set threshold
          </Button>
        ) : null,
    },
  ];
  const critical = materials.filter(isCritical).length;

  return (
    <>
      <PageHeader
        title="Stock monitoring"
        subtitle="Warehouse, production and transit quantities are read from the shared stock database."
        crumbs={[{ label: "Stock" }]}
        meta={
          <>
            <StatusBadge tone={critical ? "danger" : "ok"}>{critical} below threshold</StatusBadge>
            <StatusBadge tone="neutral">{materials.length} materials</StatusBadge>
          </>
        }
        actions={
          <>
            {can("stock.reception.write") && (
              <Button asChild variant="outline" size="sm" className="h-8">
                <Link to="/stock/reception">Record reception</Link>
              </Button>
            )}
            {can("stock.transit.write") && (
              <Button asChild variant="outline" size="sm" className="h-8">
                <Link to="/stock/transit">In-transit entries</Link>
              </Button>
            )}
          </>
        }
      />
      <div className="p-4">
        <div className="panel overflow-hidden">
          <DataTable
            rows={rows}
            columns={columns}
            rowKey={(m) => m.material_part_number}
            searchable={(m) => `${m.material_part_number} ${m.description} ${m.material_type}`}
            searchPlaceholder="Search database materials…"
            rowTone={(m) => (isCritical(m) ? "danger" : undefined)}
            toolbar={
              <Select value={filter} onValueChange={setFilter}>
                <SelectTrigger className="h-8 w-52 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All materials</SelectItem>
                  <SelectItem value="critical">Below critical threshold</SelectItem>
                  <SelectItem value="Roll">Rolls</SelectItem>
                  <SelectItem value="Component">Components</SelectItem>
                  <SelectItem value="Thread">Thread</SelectItem>
                </SelectContent>
              </Select>
            }
            emptyTitle={
              summary.isLoading
                ? "Loading stock…"
                : summary.isError
                  ? "Could not load stock"
                  : "No material matches the filter"
            }
            {...(summary.isError
              ? { emptyDescription: readApiError(summary.error, "The stock API is unavailable.") }
              : {})}
          />
        </div>
      </div>
      <ConfirmDialog
        open={edit !== null}
        onOpenChange={(open) => !open && setEdit(null)}
        title={`Critical threshold — ${edit?.material_part_number ?? ""}`}
        confirmLabel="Save threshold"
        disabled={updateThreshold.isPending || !(Number(threshold) >= 0)}
        description="This value is stored on the material record and drives the shared critical-stock alert."
        onConfirm={() => updateThreshold.mutate()}
      >
        <div className="grid gap-1.5">
          <Label className="text-xs">Threshold ({edit?.unit})</Label>
          <Input
            value={threshold}
            onChange={(event) => setThreshold(event.target.value)}
            inputMode="decimal"
            className="h-8 text-xs"
          />
        </div>
      </ConfirmDialog>
    </>
  );
}
