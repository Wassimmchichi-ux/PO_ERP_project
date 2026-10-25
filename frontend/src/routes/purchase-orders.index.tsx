import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { GitCompareArrows, Upload } from "lucide-react";
import { PageHeader } from "@/components/erp/PageHeader";
import { DataTable, type Column } from "@/components/erp/DataTable";
import { AutoBadge } from "@/components/erp/StatusBadge";
import { AccessDenied } from "@/components/erp/EmptyState";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSession } from "@/lib/erp/session";
import { fmtDate, money, nf } from "@/lib/erp/format";
import {
  fetchPurchaseOrders,
  purchaseOrdersQueryKey,
  type PurchaseOrderListItem,
} from "@/lib/erp/purchaseOrderApi";
import { readApiError } from "@/lib/erp/api";
import { pageTitle } from "@/lib/erp/appInfo";

export const Route = createFileRoute("/purchase-orders/")({
  head: () => ({
    meta: [
      { title: pageTitle("Purchase Orders") },
      {
        name: "description",
        content:
          "Purchase order register with lifecycle status, ordered, delivered and remaining quantities, versions and delivery weeks.",
      },
      { property: "og:title", content: pageTitle("Purchase Orders") },
      {
        property: "og:description",
        content: "Track every customer purchase order from intake to delivery confirmation.",
      },
    ],
  }),
  component: PoList,
});

const STATUSES = ["Unplanned", "In Progress", "Done", "Packaged", "Delivered"] as const;

function PoList() {
  const { can } = useSession();
  const navigate = useNavigate();
  const [status, setStatus] = useState<string>("all");
  const purchaseOrderQuery = useQuery({
    queryKey: purchaseOrdersQueryKey,
    queryFn: ({ signal }) => fetchPurchaseOrders(signal),
  });

  if (!can("po.view")) return <AccessDenied what="purchase order records" />;

  const rows = (purchaseOrderQuery.data?.items ?? []).filter(
    (p) => status === "all" || p.status === status,
  );

  const columns: Column<PurchaseOrderListItem>[] = [
    {
      key: "po",
      header: "PO number",
      cell: (p) => (
        <Link
          to="/purchase-orders/$poId"
          params={{ poId: String(p.po_id) }}
          className="num font-medium text-info hover:underline"
        >
          {p.po_number}
        </Link>
      ),
      sortValue: (p) => p.po_number,
    },
    {
      key: "project",
      header: "Project",
      cell: (p) => (
        <span className="text-xs">
          {p.project_code && p.project_name ? `${p.project_code} · ${p.project_name}` : "—"}
        </span>
      ),
    },
    { key: "customer", header: "JIT Customer", cell: (p) => p.jit_customer },
    {
      key: "ormCustomer",
      header: "OEM Customer",
      cell: (p) => p.oem_customer ?? "—",
    },
    {
      key: "fgpn",
      header: "FGPN",
      mono: true,
      cell: (p) => (p.fgpn_codes.length === 1 ? p.fgpn_codes[0] : `${p.fgpn_codes.length} lines`),
    },
    {
      key: "qty",
      header: "Ordered",
      align: "right",
      mono: true,
      cell: (p) => nf.format(Number(p.ordered_quantity)),
      sortValue: (p) => Number(p.ordered_quantity),
    },
    {
      key: "delivered",
      header: "Delivered",
      align: "right",
      mono: true,
      cell: (p) => nf.format(Number(p.delivered_quantity)),
    },
    {
      key: "remaining",
      header: "Remaining",
      align: "right",
      mono: true,
      cell: (p) => (
        <span
          className={Number(p.remaining_quantity) > 0 ? "font-semibold" : "text-muted-foreground"}
        >
          {nf.format(Number(p.remaining_quantity))}
        </span>
      ),
      sortValue: (p) => Number(p.remaining_quantity),
    },
    {
      key: "amount",
      header: "Open amount",
      align: "right",
      mono: true,
      cell: (p) => money(Number(p.open_amount)),
    },
    { key: "dw", header: "Del. week", mono: true, cell: (p) => p.delivery_week ?? "—" },
    {
      key: "dd",
      header: "Delivery date",
      mono: true,
      cell: (p) => fmtDate(p.delivery_date ?? undefined),
    },
    { key: "status", header: "Status", cell: (p) => <AutoBadge value={p.status} /> },
  ];

  return (
    <>
      <PageHeader
        title="Purchase orders"
        subtitle="Every stored version is immutable; corrections are submitted as a new version."
        crumbs={[{ label: "Purchase orders" }]}
        actions={
          <>
            {can("po.compare") && (
              <Button asChild variant="outline" size="sm" className="h-8">
                <Link to="/purchase-orders/compare">
                  <GitCompareArrows className="size-3.5" /> Compare versions
                </Link>
              </Button>
            )}
            {can("po.write") && (
              <Button asChild size="sm" className="h-8">
                <Link to="/po-intake">
                  <Upload className="size-3.5" /> Upload PO PDF
                </Link>
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
            rowKey={(p) => String(p.po_id)}
            searchable={(p) =>
              `${p.po_number} ${p.jit_customer} ${p.oem_customer ?? ""} ${p.contact_name} ${p.fgpn_codes.join(" ")}`
            }
            searchPlaceholder="Search PO number, customer, OEM or FGPN…"
            onRowClick={(p) =>
              void navigate({ to: "/purchase-orders/$poId", params: { poId: String(p.po_id) } })
            }
            toolbar={
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger className="h-8 w-44 text-xs">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  {STATUSES.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            }
            emptyTitle={
              purchaseOrderQuery.isLoading
                ? "Loading purchase orders…"
                : purchaseOrderQuery.isError
                  ? "Could not load purchase orders"
                  : "No purchase orders found"
            }
            emptyDescription={
              purchaseOrderQuery.isError
                ? readApiError(
                    purchaseOrderQuery.error,
                    "The purchase-order register API is unavailable.",
                  )
                : "Purchase orders appear here once a PDF has been reviewed and imported."
            }
          />
        </div>
      </div>
    </>
  );
}
