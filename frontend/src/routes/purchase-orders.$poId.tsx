import { createFileRoute, Link, useNavigate, notFound } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { FileText, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { PageHeader, Section, KeyValue } from "@/components/erp/PageHeader";
import { AutoBadge, StatusBadge } from "@/components/erp/StatusBadge";
import { AccessDenied } from "@/components/erp/EmptyState";
import { ConfirmDialog } from "@/components/erp/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSession } from "@/lib/erp/session";
import { fmtDate, fmtDateTime, money, nf } from "@/lib/erp/format";
import {
  fetchPurchaseOrder,
  deletePurchaseOrder,
  purchaseOrdersQueryKey,
} from "@/lib/erp/purchaseOrderApi";
import { apiFetch, throwApiError, readApiError } from "@/lib/erp/api";
import { pageTitle } from "@/lib/erp/appInfo";

export const Route = createFileRoute("/purchase-orders/$poId")({
  loader: async ({ params }) => {
    if (!/^\d+$/.test(params.poId)) throw notFound();
    return { poId: Number(params.poId) };
  },
  head: () => ({
    meta: [{ title: pageTitle("Purchase Order") }],
  }),
  component: PoDetail,
});

const CONFIRM_PHRASE = "confirm deletion";

function PoDetail() {
  const { poId } = Route.useLoaderData();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { can } = useSession();

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletionReason, setDeletionReason] = useState("");
  const [confirmPhrase, setConfirmPhrase] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  const poQuery = useQuery({
    queryKey: [...purchaseOrdersQueryKey, poId],
    queryFn: ({ signal }) => fetchPurchaseOrder(poId, signal),
    retry: false,
  });

  const deleteMutation = useMutation({
    mutationFn: () => deletePurchaseOrder(poId, deletionReason),
    onSuccess: () => {
      toast.success("Purchase order deleted successfully.");
      void queryClient.invalidateQueries({ queryKey: purchaseOrdersQueryKey });
      void navigate({ to: "/purchase-orders" });
    },
    onError: (err) => {
      toast.error(readApiError(err, "Failed to delete purchase order."));
    },
  });

  if (!can("po.view")) return <AccessDenied what="purchase order records" />;

  if (poQuery.isLoading) {
    return (
      <div className="p-8 text-center text-sm text-muted-foreground">
        Loading purchase order…
      </div>
    );
  }

  if (poQuery.isError) {
    return (
      <div className="p-8 text-center text-sm text-danger">
        {readApiError(poQuery.error, "Could not load purchase order.")}
      </div>
    );
  }

  const po = poQuery.data!;

  const filteredLines = useMemo(() => {
    if (!searchQuery.trim()) return po.lines;
    const q = searchQuery.trim().toLowerCase();
    return po.lines.filter(
      (l) =>
        l.fgpn_code.toLowerCase().includes(q) ||
        (l.item_number && l.item_number.toLowerCase().includes(q)) ||
        (l.description && l.description.toLowerCase().includes(q)),
    );
  }, [po.lines, searchQuery]);
  const canDelete = can("po.delete");

  async function handleViewPdf(versionId: number, fileName: string) {
    const newTab = window.open("", "_blank");
    try {
      const response = await apiFetch(`/purchase-orders/versions/${versionId}/pdf`);
      if (!response.ok) {
        newTab?.close();
        await throwApiError(response);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
      if (newTab) {
        newTab.location.href = url;
      } else {
        window.open(url, "_blank");
      }
    } catch (err) {
      newTab?.close();
      toast.error(readApiError(err, "Could not view the purchase order PDF."));
    }
  }
  const deleteReady =
    deletionReason.trim().length >= 10 &&
    confirmPhrase.trim().toLowerCase() === CONFIRM_PHRASE;

  return (
    <>
      <PageHeader
        title={`Purchase order ${po.po_number}`}
        subtitle={`${po.jit_customer} · contact ${po.contact_name}${po.reason ? ` · ${po.reason}` : ""}`}
        crumbs={[{ label: "Purchase orders", to: "/purchase-orders" }, { label: po.po_number }]}
        meta={
          <>
            <AutoBadge value={po.status} />
            {po.current_version != null && (
              <StatusBadge tone="neutral">Version V{po.current_version} (immutable)</StatusBadge>
            )}
            {po.project_code && po.project_name && (
              <span className="text-xs text-muted-foreground">
                {po.project_code} · {po.project_name}
              </span>
            )}
          </>
        }
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-1.5"
              onClick={() => {
                const currentVersion = po.versions.find((v) => v.is_current) ?? po.versions[0];
                if (currentVersion) {
                  void handleViewPdf(currentVersion.po_version_id, currentVersion.source_file_name);
                }
              }}
            >
              <FileText className="size-3.5" /> View PDF
            </Button>
            {canDelete && (
              <Button
                variant="destructive"
                size="sm"
                className="h-8"
                onClick={() => {
                  setDeletionReason("");
                  setConfirmPhrase("");
                  setDeleteOpen(true);
                }}
              >
                <Trash2 className="size-3.5" /> Delete PO
              </Button>
            )}
          </>
        }
      />

      <div className="space-y-4 p-4">
        <Section title="Header data">
          <KeyValue
            items={[
              { label: "PO number", value: <span className="num">{po.po_number}</span> },
              { label: "JIT customer", value: po.jit_customer },
              { label: "OEM customer", value: po.oem_customer ?? "—" },
              { label: "Contact name", value: po.contact_name },
              { label: "Contact email", value: po.contact_email ?? "—" },
              { label: "Contact phone", value: po.contact_phone ?? "—" },
              { label: "Document date", value: fmtDate(po.document_date ?? undefined) },
              { label: "Delivery date", value: fmtDate(po.delivery_date ?? undefined) },
              { label: "Delivery week (derived)", value: po.delivery_week ?? "—" },
              { label: "Car model", value: po.car_model ?? "—" },
              { label: "Engineering phase level", value: po.engineering_phase_level ?? "—" },
              { label: "Purchase order level", value: po.purchase_order_level ?? "—" },
              { label: "Reason of PO", value: po.reason ?? "—" },
            ]}
          />
        </Section>

        <div className="grid gap-4 lg:grid-cols-4">
          {[
            { label: "Ordered quantity", value: nf.format(Number(po.ordered_quantity)) },
            { label: "Delivered quantity", value: nf.format(Number(po.delivered_quantity)) },
            { label: "Remaining to deliver", value: nf.format(Number(po.remaining_quantity)) },
            { label: "Open amount", value: money(Number(po.open_amount)) },
          ].map((k) => (
            <div key={k.label} className="panel p-3">
              <p className="label-caps">{k.label}</p>
              <p className="num mt-1 text-lg font-semibold">{k.value}</p>
            </div>
          ))}
        </div>

        <Section
          title="Line items"
          description={
            searchQuery.trim()
              ? `Showing ${filteredLines.length} of ${po.lines.length} lines`
              : "Each line of a multi-line purchase order is stored independently."
          }
          actions={
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3 text-muted-foreground" />
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search FGPN or description…"
                className="h-7 w-56 pl-7 text-xs bg-background"
              />
            </div>
          }
        >
          {filteredLines.length === 0 ? (
            <p className="p-8 text-center text-xs text-muted-foreground">
              No line items match "{searchQuery}"
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/60">
                  <th className="label-caps px-4 py-2 text-left">Item</th>
                  <th className="label-caps px-4 py-2 text-left">FGPN</th>
                  <th className="label-caps px-4 py-2 text-left">Description</th>
                  <th className="label-caps px-4 py-2 text-right">Ordered</th>
                  <th className="label-caps px-4 py-2 text-right">Delivered</th>
                  <th className="label-caps px-4 py-2 text-right">Remaining</th>
                  <th className="label-caps px-4 py-2 text-right">Unit price</th>
                  <th className="label-caps px-4 py-2 text-right">Open amount</th>
                  <th className="label-caps px-4 py-2 text-left">Del. date</th>
                </tr>
              </thead>
              <tbody>
                {filteredLines.map((l) => (
                <tr key={l.po_line_id} className="border-b border-border last:border-0">
                  <td className="num px-4 py-1.5">{l.item_number ?? "—"}</td>
                  <td className="num px-4 py-1.5">{l.fgpn_code}</td>
                  <td className="px-4 py-1.5 text-xs">{l.description ?? "—"}</td>
                  <td className="num px-4 py-1.5 text-right">
                    {nf.format(Number(l.ordered_quantity))}
                  </td>
                  <td className="num px-4 py-1.5 text-right">
                    {nf.format(Number(l.delivered_quantity))}
                  </td>
                  <td className="num px-4 py-1.5 text-right font-semibold">
                    {nf.format(Number(l.remaining_quantity))}
                  </td>
                  <td className="num px-4 py-1.5 text-right">{money(Number(l.unit_price))}</td>
                  <td className="num px-4 py-1.5 text-right">{money(Number(l.open_amount))}</td>
                  <td className="num px-4 py-1.5">{fmtDate(l.delivery_date ?? undefined)}</td>
                </tr>
              ))}
              </tbody>
            </table>
          )}
        </Section>
      </div>

      {/* Delete confirmation dialog */}
      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete purchase order"
        confirmLabel={deleteMutation.isPending ? "Deleting…" : "Confirm deletion"}
        destructive
        disabled={!deleteReady || deleteMutation.isPending}
        description={
          <>
            You are about to permanently delete purchase order{" "}
            <strong>{po.po_number}</strong>. This action cannot be undone. The PO
            must not be linked to any simulation or launch.
          </>
        }
        onConfirm={() => deleteMutation.mutate()}
      >
        <div className="grid gap-4">
          <div className="grid gap-1.5">
            <Label className="text-xs">
              Reason for deletion{" "}
              <span className="text-muted-foreground">(mandatory, min. 10 characters)</span>
            </Label>
            <Textarea
              rows={3}
              value={deletionReason}
              onChange={(e) => setDeletionReason(e.target.value)}
              placeholder="Explain why this purchase order must be deleted…"
              className="text-xs"
            />
            {deletionReason.trim().length > 0 && deletionReason.trim().length < 10 && (
              <p className="text-xs text-danger">At least 10 characters required.</p>
            )}
          </div>

          <div className="grid gap-1.5">
            <Label className="text-xs">
              Type{" "}
              <span className="font-mono font-semibold text-foreground">{CONFIRM_PHRASE}</span>{" "}
              to enable deletion
            </Label>
            <Input
              value={confirmPhrase}
              onChange={(e) => setConfirmPhrase(e.target.value)}
              placeholder={CONFIRM_PHRASE}
              className="h-8 font-mono text-xs"
            />
          </div>
        </div>
      </ConfirmDialog>
    </>
  );
}
