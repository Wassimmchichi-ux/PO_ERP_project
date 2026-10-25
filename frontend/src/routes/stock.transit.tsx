import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil, RefreshCw, Save } from "lucide-react";
import { toast } from "sonner";
import { PageHeader, Section } from "@/components/erp/PageHeader";
import { StatusBadge } from "@/components/erp/StatusBadge";
import { AccessDenied } from "@/components/erp/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useSession } from "@/lib/erp/session";
import { nf } from "@/lib/erp/format";
import { pageTitle } from "@/lib/erp/appInfo";
import { readApiError } from "@/lib/erp/api";
import { transitStockQueryKey, updateArrivalDate, useTransitStock } from "@/lib/erp/transitStock";
import type { InTransitStock } from "@/lib/erp/transitStock";
import { stockHistoryQueryKey } from "@/lib/erp/stockApi";

const workflowLabel: Record<string, string> = {
  IN_TRANSIT: "In transit · awaiting receipt",
  AWAITING_CONFIRMATION: "Receipt entered · awaiting confirmation",
  UNLINKED_TRANSIT: "Unlinked transit record",
};

export const Route = createFileRoute("/stock/transit")({
  head: () => ({ meta: [{ title: pageTitle("In-Transit Material") }] }),
  component: TransitPage,
});

function TransitPage() {
  const { can } = useSession();
  const queryClient = useQueryClient();
  const stock = useTransitStock(can("stock.monitor"));
  const [targetDate, setTargetDate] = useState("");
  const [editing, setEditing] = useState<InTransitStock | null>(null);
  const [arrivalDate, setArrivalDate] = useState("");
  const [reason, setReason] = useState("");
  const writable = can("stock.transit.write");
  const update = useMutation({
    mutationFn: async () => {
      if (!editing || !writable) throw new Error("Arrival-date editing is unavailable.");
      return updateArrivalDate(editing.stock_unit_id, arrivalDate, reason.trim());
    },
    onSuccess: (updated) => {
      queryClient.setQueryData<InTransitStock[]>(transitStockQueryKey, (current) =>
        current?.map((item) => (item.stock_unit_id === updated.stock_unit_id ? updated : item)),
      );
      void queryClient.invalidateQueries({ queryKey: transitStockQueryKey });
      void queryClient.invalidateQueries({ queryKey: ["supplier-material-orders"] });
      void queryClient.invalidateQueries({ queryKey: stockHistoryQueryKey });
      setEditing(null);
      toast.success(
        "Expected arrival date saved. Future-stock simulations will use the revised date.",
      );
    },
    onError: (error) => toast.error(readApiError(error, "Could not update the arrival date.")),
  });

  if (!can("stock.monitor")) return <AccessDenied what="in-transit material" />;

  const entries = (stock.data ?? []).filter(
    (entry) =>
      !targetDate ||
      Boolean(entry.expected_arrival_date && entry.expected_arrival_date <= targetDate),
  );

  return (
    <>
      <PageHeader
        title="In-transit material"
        subtitle="Track supplier units from declaration through warehouse receipt entry until team-leader confirmation."
        crumbs={[{ label: "Stock", to: "/stock" }, { label: "In transit" }]}
      />
      <div className="space-y-4 p-4">
        <Section title="Open in-transit entries">
          <div className="flex flex-wrap items-end gap-3 border-b border-border p-4">
            <div className="grid gap-1.5">
              <Label htmlFor="transit-target-date">Arriving on or before</Label>
              <Input
                id="transit-target-date"
                type="date"
                value={targetDate}
                onChange={(event) => setTargetDate(event.target.value)}
              />
            </div>
            {targetDate && (
              <Button variant="ghost" onClick={() => setTargetDate("")}>
                Show all dates
              </Button>
            )}
            <Button
              variant="outline"
              disabled={stock.isFetching || update.isPending}
              onClick={() => void stock.refetch()}
            >
              <RefreshCw className="size-4" /> Refresh
            </Button>
            <p className="text-xs text-muted-foreground">
              Future-stock simulations exclude deliveries after the target date and deliveries
              without an arrival date.
            </p>
          </div>
          {stock.isPending && (
            <p className="p-4 text-sm" role="status">
              Loading in-transit stock…
            </p>
          )}
          {stock.isError && (
            <p className="p-4 text-sm text-danger" role="alert">
              {readApiError(stock.error, "Could not load in-transit stock.")} Use Refresh to try
              again.
            </p>
          )}
          {!stock.isPending && !stock.isError && entries.length === 0 && (
            <p className="p-4 text-sm text-muted-foreground">
              No in-transit entries match this date.
            </p>
          )}
          {entries.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1250px] text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/60">
                    <th className="px-4 py-2 text-left">Stock unit / Material</th>
                    <th className="px-4 py-2 text-left">Project / Supplier order</th>
                    <th className="px-4 py-2 text-left">Type</th>
                    <th className="px-4 py-2 text-right">Planned</th>
                    <th className="px-4 py-2 text-right">Warehouse entry</th>
                    <th className="px-4 py-2 text-left">Expected arrival</th>
                    <th className="px-4 py-2 text-left">Owner</th>
                    <th className="px-4 py-2 text-left">Workflow state</th>
                    {writable && <th className="px-4 py-2 text-left">Action</th>}
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <tr key={entry.stock_unit_id} className="border-b border-border">
                      <td className="px-4 py-3">
                        <span className="font-mono text-xs font-semibold">
                          {entry.stock_unit_reference ?? `#${entry.stock_unit_id}`} ·{" "}
                          {entry.material_part_number}
                        </span>
                        <p className="text-xs text-muted-foreground">{entry.description}</p>
                      </td>
                      <td className="px-4 py-3">
                        {entry.supplier_order_id ? (
                          <>
                            <p>
                              {entry.project_code} · {entry.project_name}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {entry.supplier_name} ({entry.supplier_reference}) · order #
                              {entry.supplier_order_id}
                              {entry.supplier_order_line_id
                                ? ` / line #${entry.supplier_order_line_id}`
                                : ""}
                            </p>
                          </>
                        ) : (
                          <span className="text-danger">No supplier order source</span>
                        )}
                      </td>
                      <td className="px-4 py-3">{entry.stock_unit_kind ?? "—"}</td>
                      <td className="num px-4 py-3 text-right">
                        {nf.format(Number(entry.expected_quantity))} {entry.unit}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {entry.actual_quantity == null ? (
                          <span className="text-muted-foreground">Pending</span>
                        ) : (
                          <>
                            <p className="num">
                              {nf.format(Number(entry.actual_quantity))} {entry.unit}
                            </p>
                            <p
                              className={`text-xs ${entry.compatible ? "text-muted-foreground" : "text-danger"}`}
                            >
                              {entry.compatible
                                ? "Matches plan"
                                : `${Number(entry.quantity_difference) > 0 ? "+" : ""}${nf.format(Number(entry.quantity_difference))} ${entry.unit}`}
                            </p>
                            {entry.arrival_entered_by_name && (
                              <p className="text-xs text-muted-foreground">
                                By {entry.arrival_entered_by_name}
                              </p>
                            )}
                          </>
                        )}
                      </td>
                      <td className="num px-4 py-3">
                        {entry.expected_arrival_date ?? "Not confirmed"}
                        {entry.status === "DELAYED" && <p className="text-xs text-warn">Overdue</p>}
                      </td>
                      <td className="px-4 py-3">{entry.assigned_user_name ?? "Shared stock"}</td>
                      <td className="px-4 py-3">
                        <StatusBadge
                          tone={
                            entry.workflow_status === "AWAITING_CONFIRMATION"
                              ? "warn"
                              : entry.workflow_status === "UNLINKED_TRANSIT"
                                ? "danger"
                                : "info"
                          }
                        >
                          {workflowLabel[entry.workflow_status] ??
                            entry.workflow_status.replaceAll("_", " ")}
                        </StatusBadge>
                      </td>
                      {writable && (
                        <td className="px-4 py-3">
                          {entry.workflow_status === "IN_TRANSIT" ? (
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={update.isPending}
                              aria-label={`Change arrival date for stock unit ${entry.stock_unit_id}`}
                              onClick={() => {
                                setEditing(entry);
                                setArrivalDate(entry.expected_arrival_date ?? "");
                                setReason("");
                                update.reset();
                              }}
                            >
                              <Pencil className="size-3.5" /> Change date
                            </Button>
                          ) : (
                            <span className="text-xs text-muted-foreground">
                              Locked after receipt entry
                            </span>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>
        {editing && writable && (
          <Section
            title={`Change arrival date · ${editing.material_part_number} · #${editing.stock_unit_id}`}
          >
            <form
              className="max-w-xl space-y-4 p-4"
              onSubmit={(event) => {
                event.preventDefault();
                if (arrivalDate && reason.trim()) update.mutate();
              }}
            >
              <p className="text-sm text-muted-foreground">
                Current arrival: {editing.expected_arrival_date ?? "Not confirmed"}. The previous
                date and your reason will be recorded.
              </p>
              <div className="grid gap-1.5">
                <Label htmlFor="arrival-date">Revised arrival date</Label>
                <Input
                  id="arrival-date"
                  type="date"
                  required
                  value={arrivalDate}
                  disabled={update.isPending}
                  onChange={(event) => setArrivalDate(event.target.value)}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="arrival-reason">Reason for change</Label>
                <Textarea
                  id="arrival-reason"
                  required
                  maxLength={1000}
                  value={reason}
                  disabled={update.isPending}
                  placeholder="For example: supplier confirmed a transport delay"
                  onChange={(event) => setReason(event.target.value)}
                />
              </div>
              <div className="flex gap-2">
                <Button
                  type="submit"
                  disabled={
                    update.isPending ||
                    !arrivalDate ||
                    !reason.trim() ||
                    arrivalDate === editing.expected_arrival_date
                  }
                >
                  <Save className="size-4" /> {update.isPending ? "Saving…" : "Save arrival date"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={update.isPending}
                  onClick={() => setEditing(null)}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </Section>
        )}
      </div>
    </>
  );
}
