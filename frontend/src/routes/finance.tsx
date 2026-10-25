import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { PageHeader, Section } from "@/components/erp/PageHeader";
import { DataTable, type Column } from "@/components/erp/DataTable";
import { StatusBadge } from "@/components/erp/StatusBadge";
import { AccessDenied } from "@/components/erp/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useProjectScope, useSession } from "@/lib/erp/session";
import {
  customerDeliveries,
  forecastPeriods,
  priceRecords,
  projectLabel,
  purchaseOrders,
  poAmount,
} from "@/lib/erp/data";
import { fmtDate, money, nf, periodLabel } from "@/lib/erp/format";
import type { PriceRecord } from "@/lib/erp/types";
import { pageTitle } from "@/lib/erp/appInfo";

export const Route = createFileRoute("/finance")({
  head: () => ({
    meta: [
      { title: pageTitle("Finance Follow-Up") },
      {
        name: "description",
        content:
          "Ordered versus delivered value, transport costs, forecast against actual turnover and the unit price register for finished goods and materials.",
      },
      { property: "og:title", content: pageTitle("Finance Follow-Up") },
      {
        property: "og:description",
        content: "Financial follow-up of launch orders, deliveries and price changes.",
      },
    ],
  }),
  component: FinancePage,
});

function FinancePage() {
  const { can } = useSession();
  const scope = useProjectScope();
  const [newPrice, setNewPrice] = useState("");
  const [target, setTarget] = useState<PriceRecord | null>(null);

  if (!can("finance.view")) return <AccessDenied what="financial follow-up" />;
  const writable = can("finance.write");

  const pos = purchaseOrders.filter((p) => scope.inScope(p.projectId));
  const deliveries = customerDeliveries.filter((d) => scope.inScope(d.projectId));

  const ordered = pos.reduce((s, p) => s + poAmount(p), 0);
  const deliveredValue = deliveries
    .filter((d) => d.status === "Delivered")
    .reduce((s, d) => s + d.quantity * d.unitPrice, 0);
  const pendingValue = deliveries
    .filter((d) => d.status !== "Delivered")
    .reduce((s, d) => s + d.quantity * d.unitPrice, 0);
  const transport = deliveries.reduce((s, d) => s + d.transportCost, 0);

  const maxVal = Math.max(...forecastPeriods.flatMap((f) => [f.forecast, f.actual]), 1);

  const priceColumns: Column<PriceRecord>[] = [
    { key: "scope", header: "Scope", cell: (p) => p.scope },
    {
      key: "pn",
      header: "Part number",
      mono: true,
      cell: (p) => <span className="font-medium">{p.partNumber}</span>,
      sortValue: (p) => p.partNumber,
    },
    {
      key: "desc",
      header: "Description",
      cell: (p) => <span className="text-xs">{p.description}</span>,
    },
    { key: "trim", header: "Trim style", mono: true, cell: (p) => p.trimStyle ?? "—" },
    {
      key: "price",
      header: "Unit price",
      align: "right",
      mono: true,
      cell: (p) => money(p.unitPrice),
      sortValue: (p) => p.unitPrice,
    },
    {
      key: "prev",
      header: "Previous",
      align: "right",
      mono: true,
      cell: (p) =>
        p.previousPrice === undefined ? (
          "—"
        ) : (
          <span className={p.unitPrice >= p.previousPrice ? "text-ok" : "text-danger"}>
            {money(p.previousPrice)} → {p.unitPrice >= p.previousPrice ? "+" : ""}
            {money(p.unitPrice - p.previousPrice)}
          </span>
        ),
    },
    {
      key: "eff",
      header: "Effective",
      mono: true,
      cell: (p) => fmtDate(p.effectiveDate),
      sortValue: (p) => p.effectiveDate,
    },
    { key: "by", header: "Changed by", cell: (p) => p.changedBy },
    {
      key: "actions",
      header: "",
      align: "right",
      cell: (p) =>
        writable ? (
          <Dialog
            open={target?.id === p.id}
            onOpenChange={(v) => {
              setTarget(v ? p : null);
              setNewPrice(v ? String(p.unitPrice) : "");
            }}
          >
            <DialogTrigger asChild>
              <Button size="sm" variant="outline" className="h-7 px-2 text-xs">
                Update price
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Update unit price — {p.partNumber}</DialogTitle>
              </DialogHeader>
              <div className="grid gap-3">
                <p className="text-xs text-muted-foreground">
                  The current price becomes the previous price; the change is recorded in the audit
                  trail and applies to purchase orders stored from the effective date onwards.
                </p>
                <div className="grid gap-1.5">
                  <Label className="text-xs">New unit price</Label>
                  <Input
                    value={newPrice}
                    onChange={(e) => setNewPrice(e.target.value)}
                    inputMode="decimal"
                    className="h-8 text-xs"
                  />
                </div>
              </div>
              <DialogFooter>
                <Button
                  className="h-8"
                  disabled={!(Number(newPrice) > 0)}
                  onClick={() => {
                    toast.success(
                      `Unit price for ${p.partNumber} updated to ${money(Number(newPrice))}.`,
                    );
                    setTarget(null);
                  }}
                >
                  Save new price
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        ) : null,
    },
  ];

  return (
    <>
      <PageHeader
        title="Finance follow-up"
        subtitle="Values are derived from stored purchase orders, confirmed deliveries and the price register."
        crumbs={[{ label: "Finance" }]}
      />

      <div className="space-y-4 p-4">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            {
              label: "Ordered value",
              value: money(ordered),
              hint: `${pos.length} purchase orders`,
            },
            { label: "Delivered value", value: money(deliveredValue), hint: "Customer-confirmed" },
            {
              label: "Awaiting delivery",
              value: money(pendingValue),
              hint: "Planned and pending confirmation",
            },
            { label: "Transport cost", value: money(transport), hint: "All deliveries in scope" },
          ].map((k) => (
            <div key={k.label} className="panel p-4">
              <p className="label-caps">{k.label}</p>
              <p className="num mt-1 text-xl font-semibold text-foreground">{k.value}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{k.hint}</p>
            </div>
          ))}
        </div>

        <Section
          title="Forecast versus actual turnover"
          description="Forecast is based on ordered quantities and planned delivery weeks; actual on confirmed deliveries."
        >
          <div className="space-y-2 p-4">
            {forecastPeriods.map((f) => (
              <div
                key={f.period}
                className="grid grid-cols-[110px_minmax(0,1fr)_200px] items-center gap-3"
              >
                <span className="text-xs text-muted-foreground">{periodLabel(f.period)}</span>
                <div className="space-y-1">
                  <div className="h-2.5 rounded-sm bg-muted">
                    <div
                      className="h-2.5 rounded-sm bg-info/60"
                      style={{ width: `${(f.forecast / maxVal) * 100}%` }}
                    />
                  </div>
                  <div className="h-2.5 rounded-sm bg-muted">
                    <div
                      className="h-2.5 rounded-sm bg-ok"
                      style={{ width: `${(f.actual / maxVal) * 100}%` }}
                    />
                  </div>
                </div>
                <div className="num text-right text-xs">
                  <span className="text-info">{money(f.forecast)}</span>
                  <span className="mx-1 text-muted-foreground">/</span>
                  <span className="text-ok">{money(f.actual)}</span>
                  <span className="ml-2 text-muted-foreground">
                    {f.forecast ? `${nf.format((f.actual / f.forecast) * 100)}%` : "—"}
                  </span>
                </div>
              </div>
            ))}
            <div className="flex gap-3 pt-1 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-sm bg-info/60" /> Forecast
              </span>
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-sm bg-ok" /> Actual
              </span>
            </div>
          </div>
        </Section>

        <Section title="Order value per purchase order">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/60">
                <th className="label-caps px-4 py-2 text-left">PO number</th>
                <th className="label-caps px-4 py-2 text-left">Project</th>
                <th className="label-caps px-4 py-2 text-left">Customer</th>
                <th className="label-caps px-4 py-2 text-left">Status</th>
                <th className="label-caps px-4 py-2 text-right">Order value</th>
              </tr>
            </thead>
            <tbody>
              {pos.map((p) => (
                <tr key={p.id} className="border-b border-border last:border-0">
                  <td className="num px-4 py-1.5 font-medium">{p.poNumber}</td>
                  <td className="px-4 py-1.5 text-xs">{projectLabel(p.projectId)}</td>
                  <td className="px-4 py-1.5 text-xs">{p.jitCustomer}</td>
                  <td className="px-4 py-1.5">
                    <StatusBadge tone="neutral">{p.status}</StatusBadge>
                  </td>
                  <td className="num px-4 py-1.5 text-right">{money(poAmount(p))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>

        <Section
          title="Price register"
          description="Unit prices used to value purchase orders and deliveries; every change keeps the previous value."
        >
          <DataTable
            rows={priceRecords}
            columns={priceColumns}
            rowKey={(p) => p.id}
            searchable={(p) => `${p.partNumber} ${p.description} ${p.trimStyle ?? ""}`}
            searchPlaceholder="Search part number, description or trim style…"
            emptyTitle="No price record"
          />
        </Section>
      </div>
    </>
  );
}
