import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Pencil, Plus, Save, Trash2, Truck } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { AccessDenied } from "@/components/erp/EmptyState";
import { PageHeader, Section } from "@/components/erp/PageHeader";
import { StatusBadge } from "@/components/erp/StatusBadge";
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
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, readApiError, throwApiError } from "@/lib/erp/api";
import { pageTitle } from "@/lib/erp/appInfo";
import { useSession } from "@/lib/erp/session";
import { transitStockQueryKey } from "@/lib/erp/transitStock";
import { stockHistoryQueryKey, stockSummaryQueryKey } from "@/lib/erp/stockApi";

interface ProjectOption {
  project_id: number;
  project_code: string;
  name: string;
}

interface MaterialOption {
  material_part_number: string;
  description: string;
  unit: string;
}

interface SupplierOption {
  id: string;
  list: string;
  value: string;
  detail: string | null;
  active: boolean;
}

interface SupplierLine {
  supplier_order_line_id: number;
  material_part_number: string;
  description: string;
  unit: string;
  stock_unit_kind: "ROLL" | "COMPONENT";
  stock_unit_reference: string;
  expected_quantity: string;
  expected_arrival_date: string;
  actual_quantity?: string | null;
  compatible?: boolean | null;
  quantity_difference?: string | null;
  arrival_entered_by_name?: string | null;
  arrival_entered_at?: string | null;
  stock_unit_id: number;
}

interface SupplierOrder {
  supplier_order_id: number;
  project_id: number;
  project_code: string;
  project_name: string;
  supplier_id: number;
  supplier_name: string;
  supplier_reference?: string | null;
  ordered_for_name: string;
  ordered_for_role: string;
  status: string;
  has_discrepancy: boolean;
  discrepancy_reason?: string | null;
  lines: SupplierLine[];
}

interface DraftLine {
  key: string;
  supplier_order_line_id?: number;
  stock_unit_id?: number;
  material_part_number: string;
  stock_unit_kind: "ROLL" | "COMPONENT";
  expected_quantity: string;
  expected_arrival_date: string;
}

const emptyLine = (): DraftLine => ({
  key: crypto.randomUUID(),
  material_part_number: "",
  stock_unit_kind: "COMPONENT",
  expected_quantity: "",
  expected_arrival_date: "",
});

const orderStatusLabel: Record<string, string> = {
  OPEN: "In transit · awaiting receipt",
  ARRIVAL_ENTERED: "Receipt entered · awaiting confirmation",
  CONFIRMED: "Warehouse confirmed",
  CANCELLED: "Cancelled",
};

export const Route = createFileRoute("/stock/supplier-orders")({
  head: () => ({ meta: [{ title: pageTitle("Supplier Material Arrivals") }] }),
  component: SupplierOrdersPage,
});

function SupplierOrdersPage() {
  const { can } = useSession();
  const queryClient = useQueryClient();
  const canOrder = can("supplier.order.write");
  const canEnter = can("supplier.arrival.enter");
  const canConfirm = can("supplier.arrival.confirm");
  const [projectId, setProjectId] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([emptyLine()]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [arrivalOrder, setArrivalOrder] = useState<SupplierOrder | null>(null);
  const [actualRows, setActualRows] = useState<Record<number, string>>({});
  const [confirmReason, setConfirmReason] = useState<Record<number, string>>({});

  const projects = useQuery({
    queryKey: ["projects", "supplier-orders"],
    queryFn: async () => {
      const response = await apiFetch("/projects");
      if (!response.ok) await throwApiError(response);
      return (await response.json()) as { items: ProjectOption[] };
    },
    enabled: canOrder,
  });
  const materials = useQuery({
    queryKey: ["stock-summary", "supplier-orders"],
    queryFn: async () => {
      const response = await apiFetch("/stock/summary");
      if (!response.ok) await throwApiError(response);
      return (await response.json()) as { items: MaterialOption[] };
    },
  });
  const suppliers = useQuery({
    queryKey: ["reference-lists", "suppliers"],
    queryFn: async () => {
      const response = await apiFetch("/admin/reference-lists");
      if (!response.ok) await throwApiError(response);
      const payload = (await response.json()) as { items: SupplierOption[] };
      return payload.items.filter((item) => item.list === "Suppliers" && item.active);
    },
    enabled: canOrder,
  });
  const orders = useQuery({
    queryKey: ["supplier-material-orders"],
    queryFn: async () => {
      const response = await apiFetch("/supplier-material-orders");
      if (!response.ok) await throwApiError(response);
      return (await response.json()) as { items: SupplierOrder[]; total: number };
    },
  });

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["supplier-material-orders"] });
    await queryClient.invalidateQueries({ queryKey: transitStockQueryKey });
    await queryClient.invalidateQueries({ queryKey: stockSummaryQueryKey });
    await queryClient.invalidateQueries({ queryKey: stockHistoryQueryKey });
  };
  const saveOrder = useMutation({
    mutationFn: async () => {
      const payload = {
        project_id: Number(projectId),
        supplier_id: Number(supplierId),
        lines: lines.map((line) => ({
          supplier_order_line_id: line.supplier_order_line_id,
          material_part_number: line.material_part_number,
          stock_unit_kind: line.stock_unit_kind,
          expected_quantity: Number(line.expected_quantity),
          expected_arrival_date: line.expected_arrival_date,
        })),
      };
      const response = await apiFetch(
        editingId ? `/supplier-material-orders/${editingId}` : "/supplier-material-orders",
        {
          method: editingId ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      if (!response.ok) await throwApiError(response);
      return (await response.json()) as SupplierOrder;
    },
    onSuccess: async () => {
      toast.success(editingId ? "Supplier order updated." : "Supplier order created.");
      resetForm();
      await refresh();
    },
    onError: (error) => toast.error(readApiError(error, "Could not save supplier order.")),
  });
  const removeOrder = useMutation({
    mutationFn: async (id: number) => {
      const response = await apiFetch(`/supplier-material-orders/${id}`, { method: "DELETE" });
      if (!response.ok) await throwApiError(response);
    },
    onSuccess: async () => {
      toast.success("Supplier order removed.");
      await refresh();
    },
    onError: (error) => toast.error(readApiError(error, "Could not remove supplier order.")),
  });
  const enterArrival = useMutation({
    mutationFn: async (order: SupplierOrder) => {
      const response = await apiFetch(
        `/supplier-material-orders/${order.supplier_order_id}/arrival`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            lines: order.lines.map((line) => ({
              supplier_order_line_id: line.supplier_order_line_id,
              actual_quantity: Number(actualRows[line.supplier_order_line_id]),
            })),
          }),
        },
      );
      if (!response.ok) await throwApiError(response);
    },
    onSuccess: async () => {
      setArrivalOrder(null);
      toast.success("Actual supplier units submitted for team-leader confirmation.");
      await refresh();
    },
    onError: (error) => toast.error(readApiError(error, "Could not submit the arrival.")),
  });
  const confirmArrival = useMutation({
    mutationFn: async (order: SupplierOrder) => {
      const response = await apiFetch(
        `/supplier-material-orders/${order.supplier_order_id}/confirm`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            discrepancy_reason: confirmReason[order.supplier_order_id] || null,
          }),
        },
      );
      if (!response.ok) await throwApiError(response);
    },
    onSuccess: async () => {
      toast.success("Arrival confirmed. The responsible launch engineer was notified.");
      await refresh();
    },
    onError: (error) => toast.error(readApiError(error, "Could not confirm the arrival.")),
  });

  const validPlan = useMemo(
    () =>
      Boolean(projectId && supplierId) &&
      lines.length > 0 &&
      lines.every(
        (line) =>
          line.material_part_number &&
          Number(line.expected_quantity) > 0 &&
          line.expected_arrival_date,
      ),
    [lines, projectId, supplierId],
  );

  if (!canOrder && !canEnter && !canConfirm) return <AccessDenied what="supplier arrivals" />;

  function resetForm() {
    setProjectId("");
    setSupplierId("");
    setLines([emptyLine()]);
    setEditingId(null);
  }

  function editOrder(order: SupplierOrder) {
    setEditingId(order.supplier_order_id);
    setProjectId(String(order.project_id));
    setSupplierId(String(order.supplier_id));
    setLines(
      order.lines.map((line) => ({
        key: String(line.supplier_order_line_id),
        supplier_order_line_id: line.supplier_order_line_id,
        stock_unit_id: line.stock_unit_id,
        material_part_number: line.material_part_number,
        stock_unit_kind: line.stock_unit_kind,
        expected_quantity: String(line.expected_quantity),
        expected_arrival_date: line.expected_arrival_date,
      })),
    );
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function startArrival(order: SupplierOrder) {
    setArrivalOrder(order);
    setActualRows(
      Object.fromEntries(
        order.lines.map((line) => [
          line.supplier_order_line_id,
          String(line.actual_quantity ?? line.expected_quantity),
        ]),
      ),
    );
  }

  return (
    <div className="space-y-5 pb-12">
      <PageHeader
        title="Supplier Material Arrivals"
        subtitle="Engineer declares transit → warehouse records receipt → team leader confirms warehouse stock."
        crumbs={[{ label: "Stock", to: "/stock" }, { label: "Supplier arrivals" }]}
        meta={<StatusBadge tone="info">Engineer → Personnel → Team leader</StatusBadge>}
      />

      <Section
        title="Controlled transit workflow"
        description="Transit is planning stock until physical warehouse confirmation. It may support a target-date simulation but can never be issued directly."
      >
        <div className="grid gap-3 p-4 md:grid-cols-3">
          <div className="rounded-md border p-3">
            <p className="font-semibold">1 · Engineer declares</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Select an administrator-maintained supplier, materials, quantities and ETAs. The
              system generates internal stock-unit numbers and marks them in transit.
            </p>
          </div>
          <div className="rounded-md border p-3">
            <p className="font-semibold">2 · Personnel records</p>
            <p className="mt-1 text-xs text-muted-foreground">
              At physical arrival, warehouse personnel enter the quantity received against every
              generated stock unit.
            </p>
          </div>
          <div className="rounded-md border p-3">
            <p className="font-semibold">3 · Team leader confirms</p>
            <p className="mt-1 text-xs text-muted-foreground">
              The team leader reviews discrepancies. Confirmation moves units to warehouse stock and
              notifies the responsible engineer.
            </p>
          </div>
        </div>
      </Section>

      {canOrder && (
        <Section
          title={editingId ? `Modify supplier order #${editingId}` : "Create supplier order"}
          description="Rolls and components can be entered together. Each row becomes one traceable stock unit."
        >
          <div className="space-y-4 p-4">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Project</Label>
                <Select value={projectId} onValueChange={setProjectId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select project" />
                  </SelectTrigger>
                  <SelectContent>
                    {(projects.data?.items ?? []).map((project) => (
                      <SelectItem key={project.project_id} value={String(project.project_id)}>
                        {project.project_code} · {project.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Supplier</Label>
                <Select value={supplierId} onValueChange={setSupplierId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select supplier reference" />
                  </SelectTrigger>
                  <SelectContent>
                    {(suppliers.data ?? []).map((supplier) => (
                      <SelectItem
                        key={supplier.id}
                        value={supplier.id.split(":").at(1) ?? supplier.id}
                      >
                        {supplier.detail} · {supplier.value}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {(suppliers.data?.length ?? 0) === 0 && !suppliers.isLoading && (
                  <p className="text-xs text-warn">
                    An administrator must add an active supplier reference first.
                  </p>
                )}
              </div>
            </div>

            <div className="overflow-x-auto rounded-md border">
              <table className="w-full min-w-[920px] text-xs">
                <thead className="bg-muted/60">
                  <tr>
                    <th className="px-3 py-2 text-left">Material</th>
                    <th className="px-3 py-2 text-left">Unit type</th>
                    <th className="px-3 py-2 text-left">Internal stock unit</th>
                    <th className="px-3 py-2 text-left">Expected quantity</th>
                    <th className="px-3 py-2 text-left">ETA</th>
                    <th className="w-12" />
                  </tr>
                </thead>
                <tbody>
                  {lines.map((line) => (
                    <tr key={line.key} className="border-t">
                      <td className="p-2">
                        <Select
                          value={line.material_part_number}
                          onValueChange={(value) =>
                            setLines((rows) =>
                              rows.map((row) =>
                                row.key === line.key
                                  ? { ...row, material_part_number: value }
                                  : row,
                              ),
                            )
                          }
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Material" />
                          </SelectTrigger>
                          <SelectContent>
                            {(materials.data?.items ?? []).map((material) => (
                              <SelectItem
                                key={material.material_part_number}
                                value={material.material_part_number}
                              >
                                {material.material_part_number} · {material.description}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </td>
                      <td className="p-2">
                        <Select
                          value={line.stock_unit_kind}
                          onValueChange={(value: "ROLL" | "COMPONENT") =>
                            setLines((rows) =>
                              rows.map((row) =>
                                row.key === line.key ? { ...row, stock_unit_kind: value } : row,
                              ),
                            )
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="ROLL">Roll</SelectItem>
                            <SelectItem value="COMPONENT">Component</SelectItem>
                          </SelectContent>
                        </Select>
                      </td>
                      <td className="p-2">
                        <span className="font-mono text-xs text-muted-foreground">
                          {line.stock_unit_id ? `#${line.stock_unit_id}` : "Generated on save"}
                        </span>
                      </td>
                      <td className="p-2">
                        <Input
                          type="number"
                          min="0.0001"
                          step="0.0001"
                          value={line.expected_quantity}
                          onChange={(event) =>
                            setLines((rows) =>
                              rows.map((row) =>
                                row.key === line.key
                                  ? { ...row, expected_quantity: event.target.value }
                                  : row,
                              ),
                            )
                          }
                        />
                      </td>
                      <td className="p-2">
                        <Input
                          type="date"
                          value={line.expected_arrival_date}
                          onChange={(event) =>
                            setLines((rows) =>
                              rows.map((row) =>
                                row.key === line.key
                                  ? { ...row, expected_arrival_date: event.target.value }
                                  : row,
                              ),
                            )
                          }
                        />
                      </td>
                      <td className="p-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          disabled={lines.length === 1}
                          onClick={() =>
                            setLines((rows) => rows.filter((row) => row.key !== line.key))
                          }
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap justify-between gap-2">
              <Button variant="outline" onClick={() => setLines((rows) => [...rows, emptyLine()])}>
                <Plus className="size-4" /> Add roll or component
              </Button>
              <div className="flex gap-2">
                {editingId && (
                  <Button variant="outline" onClick={resetForm}>
                    Cancel edit
                  </Button>
                )}
                <Button
                  disabled={!validPlan || saveOrder.isPending}
                  onClick={() => saveOrder.mutate()}
                >
                  <Save className="size-4" /> {editingId ? "Save changes" : "Declare in transit"}
                </Button>
              </div>
            </div>
          </div>
        </Section>
      )}

      {arrivalOrder && canEnter && (
        <Section
          title={`Enter actual receipt · ${arrivalOrder.supplier_reference ?? `#${arrivalOrder.supplier_order_id}`}`}
          description="Warehouse personnel must enter every physical unit. The system compares each value with the engineer's supplier plan."
        >
          <div className="space-y-3 p-4">
            {arrivalOrder.lines.map((line) => (
              <div
                key={line.supplier_order_line_id}
                className="grid gap-2 rounded-md border p-3 md:grid-cols-[1.4fr_1fr]"
              >
                <div>
                  <p className="font-mono text-xs font-semibold">
                    {line.stock_unit_reference} · {line.material_part_number}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {line.description} · expected {line.expected_quantity} {line.unit}
                  </p>
                </div>
                <Input
                  type="number"
                  min="0"
                  step="0.0001"
                  value={actualRows[line.supplier_order_line_id] ?? ""}
                  onChange={(event) =>
                    setActualRows((rows) => ({
                      ...rows,
                      [line.supplier_order_line_id]: event.target.value,
                    }))
                  }
                  aria-label={`Actual quantity for stock unit ${line.stock_unit_id}`}
                />
              </div>
            ))}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setArrivalOrder(null)}>
                Cancel
              </Button>
              <Button
                disabled={
                  enterArrival.isPending ||
                  arrivalOrder.lines.some((line) => {
                    const value = actualRows[line.supplier_order_line_id];
                    return (
                      value == null ||
                      value.trim() === "" ||
                      !Number.isFinite(Number(value)) ||
                      Number(value) < 0
                    );
                  })
                }
                onClick={() => enterArrival.mutate(arrivalOrder)}
              >
                Submit warehouse receipt
              </Button>
            </div>
          </div>
        </Section>
      )}

      <Section
        title="Supplier order register"
        description="Open and receipt-entered units also appear in Transit. Confirmed orders remain here as legal history after their units move to Warehouse."
      >
        {orders.isLoading ? (
          <p className="p-5 text-sm text-muted-foreground">Loading supplier orders…</p>
        ) : orders.isError ? (
          <p className="p-5 text-sm text-danger">
            {readApiError(orders.error, "Could not load supplier orders.")}
          </p>
        ) : (
          <div className="space-y-3 p-4">
            {(orders.data?.items ?? []).map((order) => (
              <div key={order.supplier_order_id} className="rounded-lg border bg-card p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">
                      {order.supplier_name} ·{" "}
                      {order.supplier_reference ?? `Order #${order.supplier_order_id}`}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Project: {order.project_code} · {order.project_name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Responsible: {order.ordered_for_name} ({order.ordered_for_role})
                    </p>
                  </div>
                  <StatusBadge
                    tone={
                      order.status === "CONFIRMED"
                        ? "ok"
                        : order.has_discrepancy
                          ? "danger"
                          : "info"
                    }
                  >
                    {orderStatusLabel[order.status] ?? order.status.replaceAll("_", " ")}
                  </StatusBadge>
                </div>
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full min-w-[760px] text-xs">
                    <thead>
                      <tr className="border-b text-left">
                        <th className="py-2">Material / unit</th>
                        <th>Internal stock unit</th>
                        <th>Expected / ETA</th>
                        <th>Actual</th>
                        <th>Match</th>
                      </tr>
                    </thead>
                    <tbody>
                      {order.lines.map((line) => (
                        <tr key={line.supplier_order_line_id} className="border-b last:border-0">
                          <td className="py-2">
                            <p className="font-mono">
                              {line.material_part_number} · {line.stock_unit_kind}
                            </p>
                            <p className="text-muted-foreground">{line.description}</p>
                          </td>
                          <td className="font-mono">{line.stock_unit_reference}</td>
                          <td>
                            {line.expected_quantity} {line.unit} · {line.expected_arrival_date}
                          </td>
                          <td>
                            {line.actual_quantity == null
                              ? "—"
                              : `${line.actual_quantity} ${line.unit}`}
                            {line.arrival_entered_by_name && (
                              <p className="text-muted-foreground">
                                By {line.arrival_entered_by_name}
                              </p>
                            )}
                          </td>
                          <td>
                            {line.compatible == null
                              ? "Pending"
                              : line.compatible
                                ? "Compatible"
                                : `Difference ${Number(line.quantity_difference) > 0 ? "+" : ""}${line.quantity_difference} ${line.unit}`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {order.status === "ARRIVAL_ENTERED" && canConfirm && order.has_discrepancy && (
                  <div className="mt-3 space-y-1.5">
                    <Label>Required discrepancy reason</Label>
                    <Textarea
                      value={confirmReason[order.supplier_order_id] ?? ""}
                      onChange={(event) =>
                        setConfirmReason((reasons) => ({
                          ...reasons,
                          [order.supplier_order_id]: event.target.value,
                        }))
                      }
                    />
                  </div>
                )}
                <div className="mt-3 flex flex-wrap justify-end gap-2">
                  {canOrder && order.status === "OPEN" && (
                    <>
                      <Button size="sm" variant="outline" onClick={() => editOrder(order)}>
                        <Pencil className="size-3.5" /> Modify
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => removeOrder.mutate(order.supplier_order_id)}
                      >
                        <Trash2 className="size-3.5" /> Remove
                      </Button>
                    </>
                  )}
                  {canEnter && (order.status === "OPEN" || order.status === "ARRIVAL_ENTERED") && (
                    <Button size="sm" onClick={() => startArrival(order)}>
                      <Truck className="size-3.5" /> Record warehouse receipt
                    </Button>
                  )}
                  {canConfirm && order.status === "ARRIVAL_ENTERED" && (
                    <Button
                      size="sm"
                      disabled={
                        confirmArrival.isPending ||
                        (order.has_discrepancy &&
                          (confirmReason[order.supplier_order_id]?.trim().length ?? 0) < 10)
                      }
                      onClick={() => confirmArrival.mutate(order)}
                    >
                      <CheckCircle2 className="size-3.5" /> Confirm warehouse arrival
                    </Button>
                  )}
                </div>
              </div>
            ))}
            {(orders.data?.items.length ?? 0) === 0 && (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No supplier material orders yet.
              </p>
            )}
          </div>
        )}
      </Section>
    </div>
  );
}
