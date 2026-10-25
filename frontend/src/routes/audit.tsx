import { createFileRoute } from "@tanstack/react-router";
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
import { useProjectScope, useSession } from "@/lib/erp/session";
import { auditEvents, projectLabel } from "@/lib/erp/data";
import { fmtDateTime } from "@/lib/erp/format";
import type { AuditEvent } from "@/lib/erp/types";
import { pageTitle } from "@/lib/erp/appInfo";

export const Route = createFileRoute("/audit")({
  head: () => ({
    meta: [
      { title: pageTitle("Audit Trail") },
      {
        name: "description",
        content:
          "Immutable trace of stock corrections, purchase order changes, launch decisions, deliveries, document uploads and access events.",
      },
      { property: "og:title", content: pageTitle("Audit Trail") },
      {
        property: "og:description",
        content: "Who did what, when, and why — across every module of the ERP prototype.",
      },
    ],
  }),
  component: AuditPage,
});

const CATEGORIES: AuditEvent["category"][] = [
  "Stock",
  "Purchase Order",
  "Simulation",
  "Launch decision",
  "Delivery",
  "Document",
  "Price",
  "BOM",
  "CutMan",
  "Access",
];

function AuditPage() {
  const { can } = useSession();
  const scope = useProjectScope();
  const [cat, setCat] = useState("all");

  if (!can("audit.view")) return <AccessDenied what="the audit trail" />;

  const rows = auditEvents
    .filter((e) => scope.inScope(e.projectId))
    .filter((e) => cat === "all" || e.category === cat)
    .slice()
    .sort((a, b) => (a.at < b.at ? 1 : -1));

  const columns: Column<AuditEvent>[] = [
    {
      key: "at",
      header: "Date / time",
      mono: true,
      cell: (e) => fmtDateTime(e.at),
      sortValue: (e) => e.at,
    },
    { key: "by", header: "User", cell: (e) => e.by },
    {
      key: "cat",
      header: "Category",
      cell: (e) => (
        <StatusBadge
          tone={
            e.category === "Launch decision"
              ? "accent"
              : e.category === "Access"
                ? "info"
                : e.category === "Stock"
                  ? "warn"
                  : "neutral"
          }
        >
          {e.category}
        </StatusBadge>
      ),
      sortValue: (e) => e.category,
    },
    { key: "event", header: "Event", cell: (e) => <span className="font-medium">{e.event}</span> },
    {
      key: "detail",
      header: "Detail",
      cell: (e) => <span className="text-xs text-muted-foreground">{e.detail}</span>,
    },
    {
      key: "project",
      header: "Project",
      cell: (e) => (
        <span className="text-xs">{e.projectId ? projectLabel(e.projectId) : "System-wide"}</span>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Audit trail"
        subtitle="Read-only record kept by the system. Entries cannot be edited or removed by any role."
        crumbs={[{ label: "Records" }, { label: "Audit trail" }]}
      />
      <div className="p-4">
        <div className="panel overflow-hidden">
          <DataTable
            rows={rows}
            columns={columns}
            rowKey={(e) => e.id}
            searchable={(e) => `${e.event} ${e.detail} ${e.by} ${e.category}`}
            searchPlaceholder="Search event, detail or user…"
            toolbar={
              <Select value={cat} onValueChange={setCat}>
                <SelectTrigger className="h-8 w-56 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All categories</SelectItem>
                  {CATEGORIES.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            }
            emptyTitle="No audit entry in scope"
          />
        </div>
      </div>
    </>
  );
}
