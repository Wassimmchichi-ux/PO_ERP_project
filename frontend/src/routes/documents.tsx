import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Download } from "lucide-react";
import { PageHeader } from "@/components/erp/PageHeader";
import { DataTable, type Column } from "@/components/erp/DataTable";
import { StatusBadge } from "@/components/erp/StatusBadge";
import { AccessDenied } from "@/components/erp/EmptyState";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useProjectScope, useSession } from "@/lib/erp/session";
import { documents, projectLabel } from "@/lib/erp/data";
import { fmtDateTime } from "@/lib/erp/format";
import type { ErpDocument } from "@/lib/erp/types";
import { pageTitle } from "@/lib/erp/appInfo";

export const Route = createFileRoute("/documents")({
  head: () => ({
    meta: [
      { title: pageTitle("Document Register") },
      {
        name: "description",
        content:
          "Central register of purchase order PDFs, BOM files, CutMan reports, meeting minutes, delivery documents and invoices, each linked to its business record.",
      },
      { property: "og:title", content: pageTitle("Document Register") },
      {
        property: "og:description",
        content: "One place for every document generated or received by the launch process.",
      },
    ],
  }),
  component: DocumentsPage,
});

const TYPES: ErpDocument["type"][] = [
  "Purchase Order PDF",
  "BOM Excel",
  "CutMan Report",
  "Meeting Minutes (PV)",
  "Simulation Draft",
  "Warehouse Delivery Document",
  "Signed Reception Document",
  "Customer Delivery Instruction",
  "Invoice",
];

function DocumentsPage() {
  const { can } = useSession();
  const scope = useProjectScope();
  const [type, setType] = useState("all");

  if (!can("documents.view")) return <AccessDenied what="the document register" />;

  const rows = documents
    .filter((d) => scope.inScope(d.projectId))
    .filter((d) => type === "all" || d.type === type);

  const columns: Column<ErpDocument>[] = [
    {
      key: "file",
      header: "File",
      cell: (d) => (
        <span>
          <span className="font-medium">{d.fileName}</span>
          {d.draft && (
            <StatusBadge tone="warn" className="ml-2">
              Draft
            </StatusBadge>
          )}
        </span>
      ),
      sortValue: (d) => d.fileName,
    },
    { key: "type", header: "Type", cell: (d) => d.type },
    { key: "v", header: "Ver.", mono: true, cell: (d) => `v${d.version}` },
    {
      key: "linked",
      header: "Linked record",
      cell: (d) => (
        <span className="text-xs">
          {d.linkedEntity.kind} · <span className="num">{d.linkedEntity.ref}</span>
        </span>
      ),
    },
    {
      key: "project",
      header: "Project",
      cell: (d) => <span className="text-xs">{projectLabel(d.projectId)}</span>,
    },
    {
      key: "uploaded",
      header: "Stored",
      mono: true,
      cell: (d) => fmtDateTime(d.uploadedAt),
      sortValue: (d) => d.uploadedAt,
    },
    { key: "by", header: "By", cell: (d) => d.uploadedBy },
    { key: "size", header: "Size", align: "right", mono: true, cell: (d) => `${d.sizeKb} kB` },
    {
      key: "actions",
      header: "",
      align: "right",
      cell: () => (
        <Button variant="outline" size="sm" className="h-7 px-2 text-xs">
          <Download className="size-3.5" /> Download
        </Button>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Document register"
        subtitle="Every document is stored centrally and linked to the record it belongs to; versions are kept."
        crumbs={[{ label: "Documents" }]}
      />
      <div className="p-4">
        <div className="panel overflow-hidden">
          <DataTable
            rows={rows}
            columns={columns}
            rowKey={(d) => d.id}
            searchable={(d) => `${d.fileName} ${d.type} ${d.linkedEntity.ref} ${d.uploadedBy}`}
            searchPlaceholder="Search file name, type or linked record…"
            toolbar={
              <Select value={type} onValueChange={setType}>
                <SelectTrigger className="h-8 w-60 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All document types</SelectItem>
                  {TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            }
            emptyTitle="No document in scope"
          />
        </div>
      </div>
    </>
  );
}
