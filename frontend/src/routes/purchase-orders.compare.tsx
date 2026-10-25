import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { PageHeader, Section } from "@/components/erp/PageHeader";
import { StatusBadge, type Tone } from "@/components/erp/StatusBadge";
import { AccessDenied, EmptyState } from "@/components/erp/EmptyState";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { useSession } from "@/lib/erp/session";
import { fmtDateTime } from "@/lib/erp/format";
import { pageTitle } from "@/lib/erp/appInfo";
import {
  fetchPurchaseOrders,
  fetchPurchaseOrder,
  fetchPoComparison,
  purchaseOrdersQueryKey,
  type VersionComparisonRow,
} from "@/lib/erp/purchaseOrderApi";

interface CompareSearch {
  poId?: string | undefined;
}

export const Route = createFileRoute("/purchase-orders/compare")({
  validateSearch: (search: Record<string, unknown>): CompareSearch => ({
    poId: typeof search["poId"] === "string" ? (search["poId"] as string) : undefined,
  }),
  head: () => ({
    meta: [
      { title: pageTitle("PO Version Comparison") },
      {
        name: "description",
        content:
          "Field-by-field comparison between two stored versions of the same purchase order, with changed, added and removed indicators.",
      },
      { property: "og:title", content: pageTitle("PO Version Comparison") },
      {
        property: "og:description",
        content: "Compare stored purchase order versions without altering the original records.",
      },
    ],
  }),
  component: ComparePage,
});

type ChangeStatus = "Unchanged" | "Changed" | "Added" | "Removed";
const TONE: Record<ChangeStatus, Tone> = {
  Unchanged: "neutral",
  Changed: "warn",
  Added: "ok",
  Removed: "danger",
};

function ComparePage() {
  const { can } = useSession();
  const search = Route.useSearch();

  // 1. Fetch real POs from backend
  const { data: poListData } = useQuery({
    queryKey: purchaseOrdersQueryKey,
    queryFn: () => fetchPurchaseOrders(),
  });
  const poList = poListData?.items ?? [];

  // 2. Select initial PO: from search param or first available
  const [selectedPoId, setSelectedPoId] = useState<string>(() => search.poId ?? "");

  const activePoId = selectedPoId || search.poId || (poList[0] ? String(poList[0].po_id) : "");

  // 3. Fetch detailed PO to get all stored versions
  const { data: poDetail } = useQuery({
    queryKey: ["purchase-order", activePoId],
    queryFn: () => fetchPurchaseOrder(activePoId),
    enabled: Boolean(activePoId),
  });

  const versions = poDetail?.versions ?? [];

  const [a, setA] = useState<string>("1");
  const [b, setB] = useState<string>("2");

  // Sync version selections when versions load
  useEffect(() => {
    if (versions.length >= 2) {
      const sorted = [...versions].sort((v1, v2) => v1.version_number - v2.version_number);
      const first = sorted[0];
      const last = sorted[sorted.length - 1];
      if (first) setA(String(first.version_number));
      if (last) setB(String(last.version_number));
    } else if (versions.length === 1) {
      const only = versions[0];
      if (only) {
        setA(String(only.version_number));
        setB(String(only.version_number));
      }
    }
  }, [versions]);

  // 4. Fetch comparison rows from database/backend
  const { data: comparisonResult } = useQuery({
    queryKey: ["po-comparison", activePoId, a, b],
    queryFn: () => fetchPoComparison(activePoId, a, b),
    enabled: Boolean(activePoId && a && b && versions.length >= 2),
  });

  const rows: VersionComparisonRow[] = comparisonResult?.rows ?? [];

  if (!can("po.view")) return <AccessDenied what="purchase order version comparison" />;

  return (
    <>
      <PageHeader
        title="Purchase order version comparison"
        subtitle="Versions are linked by purchase order number and are never overwritten."
        crumbs={[
          { label: "Purchase orders", to: "/purchase-orders" },
          { label: "Compare versions" },
        ]}
      />
      <div className="space-y-4 p-4">
        <Section title="Select versions">
          <div className="grid gap-3 p-4 md:grid-cols-3">
            <div className="grid gap-1.5">
              <Label className="text-xs">Purchase order</Label>
              <Select
                value={activePoId}
                onValueChange={(v) => {
                  setSelectedPoId(v);
                  setA("1");
                  setB("2");
                }}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Select purchase order…" />
                </SelectTrigger>
                <SelectContent>
                  {poList.map((p) => (
                    <SelectItem key={p.po_id} value={String(p.po_id)}>
                      {p.po_number} — {p.project_code ?? p.project_name ?? "No Project"}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label className="text-xs">Version A</Label>
              <Select value={a} onValueChange={setA}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {versions.map((v) => (
                    <SelectItem key={v.po_version_id} value={String(v.version_number)}>
                      V{v.version_number} — stored {fmtDateTime(v.created_at)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label className="text-xs">Version B</Label>
              <Select value={b} onValueChange={setB}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {versions.map((v) => (
                    <SelectItem key={v.po_version_id} value={String(v.version_number)}>
                      V{v.version_number} — stored {fmtDateTime(v.created_at)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </Section>

        <Section
          title="Comparison grid"
          description={
            poDetail ? `${poDetail.po_number} · V${a} against V${b}` : "No purchase order selected"
          }
        >
          {!poDetail || versions.length < 2 ? (
            <EmptyState
              title="Only one version stored"
              description="A comparison requires at least two stored versions of the same purchase order number."
            />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/60">
                  <th className="label-caps px-4 py-2 text-left">Field</th>
                  <th className="label-caps px-4 py-2 text-left">Value in V{a}</th>
                  <th className="label-caps px-4 py-2 text-left">Value in V{b}</th>
                  <th className="label-caps px-4 py-2 text-left">Change</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    key={r.field}
                    className={`border-b border-border last:border-0 ${
                      r.status !== "Unchanged" ? "bg-warn-soft/40" : ""
                    }`}
                  >
                    <td className="px-4 py-1.5 font-medium">{r.field}</td>
                    <td className="num px-4 py-1.5">{r.a === null ? "—" : String(r.a)}</td>
                    <td className="num px-4 py-1.5">{r.b === null ? "—" : String(r.b)}</td>
                    <td className="px-4 py-1.5">
                      <StatusBadge tone={TONE[r.status]}>{r.status}</StatusBadge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>
      </div>
    </>
  );
}
