import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Play } from "lucide-react";
import { PageHeader } from "@/components/erp/PageHeader";
import { DataTable, type Column } from "@/components/erp/DataTable";
import { AutoBadge, StatusBadge } from "@/components/erp/StatusBadge";
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
import { findPo, projectLabel, simulations } from "@/lib/erp/data";
import { fmtDateTime, nf } from "@/lib/erp/format";
import type { Simulation } from "@/lib/erp/types";
import { pageTitle } from "@/lib/erp/appInfo";

export const Route = createFileRoute("/simulations/")({
  head: () => ({
    meta: [
      { title: pageTitle("Material Simulations") },
      {
        name: "description",
        content:
          "Feasibility simulations comparing bill-of-material requirements against warehouse, in-transit and cutting-area stock before a launch decision.",
      },
      { property: "og:title", content: pageTitle("Material Simulations") },
      {
        property: "og:description",
        content:
          "Decision support for launch feasibility, shortfalls and maximum launchable quantity.",
      },
    ],
  }),
  component: SimulationList,
});

function SimulationList() {
  const { can } = useSession();
  const scope = useProjectScope();
  const navigate = useNavigate();
  const [feas, setFeas] = useState("all");

  if (!can("simulation.view")) return <AccessDenied what="simulation results" />;

  const rows = simulations
    .filter((s) => scope.inScope(s.projectId))
    .filter((s) => feas === "all" || s.feasibility === feas);

  const columns: Column<Simulation>[] = [
    {
      key: "ref",
      header: "Simulation",
      cell: (s) => (
        <Link
          to="/simulations/$simId"
          params={{ simId: s.id }}
          className="num font-medium text-info hover:underline"
        >
          {s.ref}
        </Link>
      ),
      sortValue: (s) => s.ref,
    },
    {
      key: "project",
      header: "Project",
      cell: (s) => <span className="text-xs">{projectLabel(s.projectId)}</span>,
    },
    {
      key: "mode",
      header: "Mode",
      cell: (s) => (
        <StatusBadge tone="info" dot={false}>
          {s.mode}
        </StatusBadge>
      ),
    },
    {
      key: "pos",
      header: "Purchase orders",
      cell: (s) => (
        <span className="num text-xs">
          {s.poIds.map((id) => findPo(id)?.poNumber ?? id).join(", ") || "—"}
        </span>
      ),
    },
    {
      key: "coef",
      header: "Safety coef.",
      align: "right",
      mono: true,
      cell: (s) => `×${s.safetyCoefficient}`,
    },
    {
      key: "future",
      header: "Future stock",
      cell: (s) => (
        <StatusBadge tone={s.includeFutureStock ? "info" : "neutral"} dot={false}>
          {s.includeFutureStock ? "Included" : "Excluded"}
        </StatusBadge>
      ),
    },
    {
      key: "short",
      header: "Materials short",
      align: "right",
      mono: true,
      cell: (s) => {
        const n = s.requirements.filter((r) => r.shortfall > 0).length;
        return (
          <span className={n > 0 ? "font-semibold text-danger" : "text-muted-foreground"}>
            {n} / {s.requirements.length}
          </span>
        );
      },
      sortValue: (s) => s.requirements.filter((r) => r.shortfall > 0).length,
    },
    {
      key: "max",
      header: "Max launchable",
      align: "right",
      mono: true,
      cell: (s) => (s.maxLaunchableQty === undefined ? "—" : nf.format(s.maxLaunchableQty)),
    },
    { key: "feas", header: "Feasibility", cell: (s) => <AutoBadge value={s.feasibility} /> },
    {
      key: "pv",
      header: "Launch decision",
      cell: (s) =>
        s.approved ? (
          <StatusBadge tone="ok">Approved (PV attached)</StatusBadge>
        ) : s.meetingMinutesDocId ? (
          <StatusBadge tone="warn">PV attached — awaiting approval</StatusBadge>
        ) : (
          <StatusBadge tone="neutral">No meeting minutes</StatusBadge>
        ),
    },
    {
      key: "run",
      header: "Run at",
      mono: true,
      cell: (s) => fmtDateTime(s.runAt),
      sortValue: (s) => s.runAt,
    },
  ];

  return (
    <>
      <PageHeader
        title="Material simulations"
        subtitle="A simulation never changes stock — it produces a decision document for the launch meeting."
        crumbs={[{ label: "Simulations" }]}
        actions={
          can("simulation.run") && (
            <Button asChild size="sm" className="h-8">
              <Link to="/simulations/new">
                <Play className="size-3.5" /> New simulation
              </Link>
            </Button>
          )
        }
      />
      <div className="p-4">
        <div className="panel overflow-hidden">
          <DataTable
            rows={rows}
            columns={columns}
            rowKey={(s) => s.id}
            searchable={(s) =>
              `${s.ref} ${s.mode} ${s.runBy} ${s.poIds.map((id) => findPo(id)?.poNumber ?? "").join(" ")}`
            }
            searchPlaceholder="Search simulation, PO number or user…"
            onRowClick={(s) =>
              void navigate({ to: "/simulations/$simId", params: { simId: s.id } })
            }
            rowTone={(s) =>
              s.feasibility === "Not feasible"
                ? "danger"
                : s.feasibility === "Partially feasible"
                  ? "warn"
                  : undefined
            }
            toolbar={
              <Select value={feas} onValueChange={setFeas}>
                <SelectTrigger className="h-8 w-52 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All feasibility results</SelectItem>
                  <SelectItem value="Fully feasible">Fully feasible</SelectItem>
                  <SelectItem value="Partially feasible">Partially feasible</SelectItem>
                  <SelectItem value="Not feasible">Not feasible</SelectItem>
                </SelectContent>
              </Select>
            }
            emptyTitle="No simulation recorded"
            emptyDescription="Run a simulation from a confirmed purchase order to evaluate launch feasibility."
          />
        </div>
      </div>
    </>
  );
}
