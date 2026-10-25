import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Boxes, Layers, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { PageHeader, Section } from "@/components/erp/PageHeader";
import { StatusBadge } from "@/components/erp/StatusBadge";
import { AccessDenied } from "@/components/erp/EmptyState";
import { ConfirmDialog } from "@/components/erp/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
  fetchStockHistory,
  fetchStockSummary,
  materialCategory,
  stockHistoryQueryKey,
  stockSummaryQueryKey,
  type StockMovementItem,
} from "@/lib/erp/stockApi";
import { fmtDateTime, nf } from "@/lib/erp/format";
import { pageTitle } from "@/lib/erp/appInfo";

export const Route = createFileRoute("/stock/reception")({
  head: () => ({ meta: [{ title: pageTitle("Material Reception") }] }),
  component: ReceptionPage,
});

type ReceptionMode = "rolls" | "components" | null;
interface QuantityRow {
  id: string;
  quantity: string;
}

const newQuantity = (): QuantityRow => ({ id: crypto.randomUUID(), quantity: "" });
const ageHours = (date: string) => (Date.now() - new Date(date).getTime()) / 3_600_000;

function ReceptionPage() {
  const { can } = useSession();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<ReceptionMode>(null);
  const [partNumber, setPartNumber] = useState("");
  const [quantities, setQuantities] = useState<QuantityRow[]>([newQuantity()]);
  const [sourceReference, setSourceReference] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [correcting, setCorrecting] = useState<StockMovementItem | null>(null);
  const [correctedQuantity, setCorrectedQuantity] = useState("");
  const [reason, setReason] = useState("");
  const summary = useQuery({
    queryKey: stockSummaryQueryKey,
    queryFn: ({ signal }) => fetchStockSummary(signal),
  });
  const history = useQuery({
    queryKey: stockHistoryQueryKey,
    queryFn: ({ signal }) => fetchStockHistory(signal),
  });

  const refreshStock = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: stockSummaryQueryKey }),
      queryClient.invalidateQueries({ queryKey: stockHistoryQueryKey }),
    ]);
  };
  const reception = useMutation({
    mutationFn: async () => {
      const response = await apiFetch("/stock/units/receptions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          material_part_number: partNumber,
          quantities: quantities.map((row) => Number(row.quantity)),
          source_reference: sourceReference.trim() || null,
        }),
      });
      if (!response.ok) await throwApiError(response);
      return (await response.json()) as { stock_unit_count: number; total_quantity: string };
    },
    onSuccess: async (result) => {
      setConfirm(false);
      setQuantities([newQuantity()]);
      setSourceReference("");
      toast.success(`${result.stock_unit_count} stock unit(s) received into warehouse.`);
      await refreshStock();
    },
    onError: (error) => toast.error(readApiError(error, "Could not post the reception.")),
  });
  const correction = useMutation({
    mutationFn: async () => {
      if (!correcting?.stock_unit_id) throw new Error("The stock unit is missing.");
      const response = await apiFetch(`/stock/units/${correcting.stock_unit_id}/reception`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quantity: Number(correctedQuantity), reason }),
      });
      if (!response.ok) await throwApiError(response);
    },
    onSuccess: async () => {
      setCorrecting(null);
      toast.success("Reception corrected; the original entry remains in history.");
      await refreshStock();
    },
    onError: (error) => toast.error(readApiError(error, "Could not correct the reception.")),
  });

  if (!can("stock.reception.write")) return <AccessDenied what="material reception" />;

  const materials = summary.data?.items ?? [];
  const selected = materials.find((item) => item.material_part_number === partNumber);
  const eligibleMaterials = materials.filter((item) =>
    mode === "rolls"
      ? materialCategory(item.material_type, item.unit) === "Roll"
      : materialCategory(item.material_type, item.unit) !== "Roll",
  );
  const total = quantities.reduce((sum, row) => sum + (Number(row.quantity) || 0), 0);
  const valid =
    Boolean(selected) &&
    quantities.length > 0 &&
    quantities.every((row) => Number(row.quantity) > 0);
  const allMovements = history.data?.items ?? [];
  const latestCorrectionByUnit = new Map<number, number>();
  for (const movement of allMovements) {
    if (movement.movement_type === "RECEPTION_CORRECTED" && movement.stock_unit_id) {
      latestCorrectionByUnit.set(
        movement.stock_unit_id,
        (latestCorrectionByUnit.get(movement.stock_unit_id) ?? 0) +
          Number(movement.quantity_change),
      );
    }
  }
  const recent = allMovements
    .filter((movement) => movement.movement_type === "WAREHOUSE_RECEPTION")
    .slice(0, 30);

  const chooseMode = (nextMode: Exclude<ReceptionMode, null>) => {
    const category = nextMode === "rolls" ? "Roll" : "Component";
    const first = materials.find((item) =>
      category === "Roll"
        ? materialCategory(item.material_type, item.unit) === "Roll"
        : materialCategory(item.material_type, item.unit) !== "Roll",
    );
    setMode(nextMode);
    setPartNumber(first?.material_part_number ?? "");
    setQuantities([newQuantity()]);
  };

  if (!mode) {
    const rolls = materials.filter(
      (item) => materialCategory(item.material_type, item.unit) === "Roll",
    );
    const components = materials.filter(
      (item) => materialCategory(item.material_type, item.unit) !== "Roll",
    );
    return (
      <>
        <PageHeader
          title="Stock Reception Hub"
          subtitle="Select the physical stock-unit category. Materials and quantities come from the shared database."
          crumbs={[{ label: "Stock", to: "/stock" }, { label: "Reception" }]}
          meta={<StatusBadge tone="neutral">{materials.length} database materials</StatusBadge>}
        />
        <div className="grid gap-6 p-6 md:grid-cols-2">
          <Button
            variant="outline"
            className="h-auto justify-start p-6 text-left"
            disabled={summary.isLoading || rolls.length === 0}
            onClick={() => chooseMode("rolls")}
          >
            <Layers className="mr-4 size-9 text-accent" />
            <span>
              <span className="block text-base font-semibold">Roll reception</span>
              <span className="mt-1 block text-xs text-muted-foreground">
                {rolls.length} roll material reference(s). Each quantity row creates one indivisible
                StockUnit.
              </span>
            </span>
          </Button>
          <Button
            variant="outline"
            className="h-auto justify-start p-6 text-left"
            disabled={summary.isLoading || components.length === 0}
            onClick={() => chooseMode("components")}
          >
            <Boxes className="mr-4 size-9 text-info" />
            <span>
              <span className="block text-base font-semibold">Components and accessories</span>
              <span className="mt-1 block text-xs text-muted-foreground">
                {components.length} component reference(s). Each row creates a traceable package
                StockUnit.
              </span>
            </span>
          </Button>
          {summary.isError && (
            <p className="col-span-full text-sm text-danger">
              {readApiError(summary.error, "Could not load database materials.")}
            </p>
          )}
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={mode === "rolls" ? "Roll reception" : "Component reception"}
        subtitle="The reception creates generated StockUnit IDs, updates warehouse totals and writes stock history in one transaction."
        crumbs={[{ label: "Stock", to: "/stock" }, { label: "Reception" }]}
        actions={
          <Button variant="outline" size="sm" className="h-8" onClick={() => setMode(null)}>
            <ArrowLeft className="mr-1 size-3.5" />
            Reception hub
          </Button>
        }
      />
      <div className="grid gap-4 p-4 lg:grid-cols-[420px_minmax(0,1fr)]">
        <Section title="New reception">
          <div className="space-y-4 p-4">
            <div className="grid gap-1.5">
              <Label className="text-xs">Material</Label>
              <Select value={partNumber} onValueChange={setPartNumber}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Select a material" />
                </SelectTrigger>
                <SelectContent>
                  {eligibleMaterials.map((item) => (
                    <SelectItem key={item.material_part_number} value={item.material_part_number}>
                      {item.material_part_number} — {item.description}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs">Physical StockUnits</Label>
                <span className="text-[11px] text-muted-foreground">
                  IDs generated after posting
                </span>
              </div>
              {quantities.map((row, index) => (
                <div key={row.id} className="flex items-end gap-2 rounded-md border p-2">
                  <div className="grid flex-1 gap-1">
                    <Label className="text-[11px] text-muted-foreground">
                      {mode === "rolls" ? `Roll ${index + 1}` : `Package ${index + 1}`} quantity (
                      {selected?.unit ?? ""})
                    </Label>
                    <Input
                      className="h-8 text-xs"
                      inputMode="decimal"
                      value={row.quantity}
                      onChange={(event) =>
                        setQuantities((current) =>
                          current.map((item) =>
                            item.id === row.id ? { ...item, quantity: event.target.value } : item,
                          ),
                        )
                      }
                    />
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0"
                    disabled={quantities.length === 1}
                    onClick={() =>
                      setQuantities((current) => current.filter((item) => item.id !== row.id))
                    }
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              ))}
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => setQuantities((current) => [...current, newQuantity()])}
              >
                <Plus className="mr-1 size-3.5" />
                Add {mode === "rolls" ? "roll" : "package"}
              </Button>
            </div>
            <div className="grid gap-1.5">
              <Label className="text-xs">Delivery note / source reference (optional)</Label>
              <Input
                className="h-8 text-xs"
                value={sourceReference}
                onChange={(event) => setSourceReference(event.target.value)}
              />
            </div>
            <div className="rounded-md border bg-muted/40 p-3 text-xs">
              <div className="flex justify-between">
                <span>Total reception</span>
                <span className="num font-semibold">
                  {nf.format(total)} {selected?.unit ?? ""}
                </span>
              </div>
              <div className="mt-1 flex justify-between text-muted-foreground">
                <span>Generated StockUnits</span>
                <span>{quantities.length}</span>
              </div>
            </div>
            <Button
              className="h-8 w-full"
              disabled={!valid || reception.isPending}
              onClick={() => setConfirm(true)}
            >
              Post reception
            </Button>
          </div>
        </Section>
        <Section
          title="Recent manual receptions"
          description="Values come from the immutable stock ledger; corrections create an additional ledger row."
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/60">
                  <th className="label-caps px-3 py-2 text-left">Received</th>
                  <th className="label-caps px-3 py-2 text-left">StockUnit</th>
                  <th className="label-caps px-3 py-2 text-left">Material</th>
                  <th className="label-caps px-3 py-2 text-right">Current qty</th>
                  <th className="label-caps px-3 py-2 text-left">By / source</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {recent.map((movement) => {
                  const current =
                    Number(movement.quantity_change) +
                    (movement.stock_unit_id
                      ? (latestCorrectionByUnit.get(movement.stock_unit_id) ?? 0)
                      : 0);
                  const withinWindow = ageHours(movement.occurred_at) <= 24;
                  const allowed = Boolean(
                    movement.stock_unit_id &&
                    (withinWindow ? can("stock.correct24h") : can("stock.correctLocked")),
                  );
                  return (
                    <tr key={movement.movement_id} className="border-b last:border-0">
                      <td className="num px-3 py-2">{fmtDateTime(movement.occurred_at)}</td>
                      <td className="num px-3 py-2">{movement.stock_unit_reference ?? "—"}</td>
                      <td className="num px-3 py-2">{movement.material_part_number}</td>
                      <td className="num px-3 py-2 text-right font-semibold">
                        {nf.format(current)} {movement.unit}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        <div>{movement.actor_name}</div>
                        <div className="text-muted-foreground">
                          {movement.source_reference ?? "No delivery reference"}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-xs"
                          disabled={!allowed}
                          onClick={() => {
                            setCorrecting(movement);
                            setCorrectedQuantity(String(current));
                            setReason("");
                          }}
                        >
                          Correct
                        </Button>
                      </td>
                    </tr>
                  );
                })}
                {recent.length === 0 && (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-3 py-10 text-center text-sm text-muted-foreground"
                    >
                      {history.isLoading
                        ? "Loading receptions…"
                        : "No manual reception has been posted yet."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Section>
      </div>
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="Post reception to warehouse"
        confirmLabel="Post reception"
        disabled={reception.isPending}
        description={`${quantities.length} physical StockUnit(s), totaling ${nf.format(total)} ${selected?.unit ?? ""}, will be added to warehouse stock and history.`}
        onConfirm={() => reception.mutate()}
      />
      <ConfirmDialog
        open={correcting !== null}
        onOpenChange={(open) => !open && setCorrecting(null)}
        title={`Correct ${correcting?.stock_unit_reference ?? "reception"}`}
        confirmLabel="Apply correction"
        disabled={
          correction.isPending || !(Number(correctedQuantity) > 0) || reason.trim().length < 10
        }
        description="The StockUnit quantity changes, while the original reception remains visible in stock history."
        onConfirm={() => correction.mutate()}
      >
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label className="text-xs">Corrected quantity</Label>
            <Input
              value={correctedQuantity}
              onChange={(event) => setCorrectedQuantity(event.target.value)}
              inputMode="decimal"
              className="h-8 text-xs"
            />
          </div>
          <div className="grid gap-1.5">
            <Label className="text-xs">Reason (minimum 10 characters)</Label>
            <Textarea
              rows={3}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              className="text-xs"
            />
          </div>
        </div>
      </ConfirmDialog>
    </>
  );
}
