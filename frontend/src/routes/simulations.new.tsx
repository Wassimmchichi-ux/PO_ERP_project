import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarDays, CheckCircle2, ChevronDown, ChevronRight, FileDown, Play, Save } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { AccessDenied } from "@/components/erp/EmptyState";
import { PageHeader, Section } from "@/components/erp/PageHeader";
import {
  SimulationFgpnPlanner,
  type PlannerFgpnItem,
} from "@/components/erp/SimulationFgpnPlanner";
import { StatusBadge } from "@/components/erp/StatusBadge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { apiFetch, readApiError, throwApiError } from "@/lib/erp/api";
import { pageTitle } from "@/lib/erp/appInfo";
import { exportSimulationToPdf } from "@/lib/erp/pdfExport";
import { useSession } from "@/lib/erp/session";

interface ProjectOption {
  project_id: number;
  project_code: string;
  name: string;
  launch_engineer_user_id: string;
  status: string;
}

interface SimulationOption {
  po_id: number;
  po_number: string;
  po_line_id: number;
  fgpn_id: number;
  fgpn_code: string;
  description?: string | null;
  ordered_quantity: string;
  already_planned_quantity: string;
  outstanding_quantity: string;
}

interface MaterialSummary {
  material_part_number: string;
  description: string;
  unit: string;
  total_demand: string;
  warehouse_stock: string;
  in_transit: string;
  cutman_wip: string;
  available_stock: string;
  allocated_quantity: string;
  shortfall: string;
  status: string;
}

interface FgpnSummary {
  po_id: number;
  po_line_id: number;
  fgpn_code: string;
  simulation_quantity: string;
  launchable_quantity: string;
  priority: number;
  coverage_percent: string;
  status: string;
}

interface AllocationDetail {
  stock_unit_id: number;
  business_unit_id?: string | null;
  material_part_number: string;
  source: string;
  is_whole_issue: boolean;
  available_quantity: string;
  allocated_quantity: string;
  remaining_quantity: string;
  expected_arrival_date?: string | null;
}

interface SimulationPreview {
  target_date?: string | null;
  stock_scope: string;
  stock_scope_mode: string;
  is_feasible: boolean;
  total_requested_quantity: string;
  total_launchable_quantity: string;
  suggestion?: string | null;
  material_summaries: MaterialSummary[];
  fgpn_summaries: FgpnSummary[];
  allocation_details: AllocationDetail[];
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

export const Route = createFileRoute("/simulations/new")({
  head: () => ({
    meta: [
      { title: pageTitle("Run & Save Simulation") },
      { name: "description", content: "Run the authoritative multi-PO material simulation." },
    ],
  }),
  component: NewSimulation,
});

function NewSimulation() {
  const { can, user } = useSession();
  const [projectId, setProjectId] = useState("");
  const [restrictToOwnStock, setRestrictToOwnStock] = useState(true);
  const [includeGlobalStock, setIncludeGlobalStock] = useState(false);
  const [includeTransit, setIncludeTransit] = useState(false);
  const [targetDate, setTargetDate] = useState("");
  const [coefficient, setCoefficient] = useState("2");
  const [plannerItems, setPlannerItems] = useState<PlannerFgpnItem[]>([]);
  const [preview, setPreview] = useState<SimulationPreview | null>(null);
  const [collapsedPos, setCollapsedPos] = useState<Set<number>>(new Set());

  const toggleHidePo = (poId: number) => {
    setCollapsedPos((prev) => {
      const next = new Set(prev);
      if (next.has(poId)) next.delete(poId);
      else next.add(poId);
      return next;
    });
  };

  const projects = useQuery({
    queryKey: ["projects", "simulation"],
    queryFn: async () => {
      const response = await apiFetch("/projects");
      if (!response.ok) await throwApiError(response);
      return (await response.json()) as { items: ProjectOption[] };
    },
    enabled: can("simulation.run"),
  });
  const project = projects.data?.items.find((item) => String(item.project_id) === projectId);
  const options = useQuery({
    queryKey: ["simulation-options", projectId],
    queryFn: async () => {
      const response = await apiFetch(`/simulations/options/${projectId}`);
      if (!response.ok) await throwApiError(response);
      return (await response.json()) as { project_id: number; lines: SimulationOption[] };
    },
    enabled: Boolean(projectId),
  });

  const selectedKeys = useMemo(() => new Set(plannerItems.map((item) => item.id)), [plannerItems]);
  const groupedOptions = useMemo(() => {
    const groups = new Map<number, { poNumber: string; lines: SimulationOption[] }>();
    for (const line of options.data?.lines ?? []) {
      const group = groups.get(line.po_id) ?? { poNumber: line.po_number, lines: [] };
      group.lines.push(line);
      groups.set(line.po_id, group);
    }
    return [...groups.entries()];
  }, [options.data]);

  const requestPayload = useMemo(
    () => ({
      project_id: Number(projectId),
      fgpns: plannerItems.map((item) => {
        const option = options.data?.lines.find(
          (line) => `${line.po_id}::${line.po_line_id}` === item.id,
        );
        return {
          po_id: Number(item.poId),
          fgpn_id: option?.fgpn_id,
          po_line_id: Number(item.lineId),
          priority: item.priorityIndex,
          requested_quantity: item.simQty,
        };
      }),
      include_in_transit: includeTransit,
      target_date: includeTransit ? targetDate : null,
      safety_coefficient: Number(coefficient),
      stock_scope_mode: restrictToOwnStock ? "OWNED_ONLY" : "ALL",
      stock_owner_user_id: restrictToOwnStock ? project?.launch_engineer_user_id : null,
      include_global_stock: restrictToOwnStock && includeGlobalStock,
    }),
    [
      coefficient,
      includeGlobalStock,
      includeTransit,
      options.data,
      plannerItems,
      project?.launch_engineer_user_id,
      projectId,
      restrictToOwnStock,
      targetDate,
    ],
  );

  const runnable = Boolean(
    projectId &&
    plannerItems.length > 0 &&
    plannerItems.every(
      (item) => Number.isInteger(item.simQty) && item.simQty > 0 && item.simQty <= item.defaultQty,
    ) &&
    Number(coefficient) >= 1 &&
    (!includeTransit || targetDate),
  );
  const runPreview = useMutation({
    mutationFn: async () => {
      const response = await apiFetch("/simulations/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestPayload),
      });
      if (!response.ok) await throwApiError(response);
      return (await response.json()) as SimulationPreview;
    },
    onSuccess: (result) => {
      setPreview(result);
      const byKey = new Map(
        result.fgpn_summaries.map((summary) => [
          `${summary.po_id}::${summary.po_line_id}`,
          summary,
        ]),
      );
      setPlannerItems((items) =>
        items.map((item) => {
          const summary = byKey.get(item.id);
          return {
            ...item,
            ...(summary
              ? {
                  coveragePercent: Number(summary.coverage_percent),
                  launchableQty: Number(summary.launchable_quantity),
                }
              : {}),
          };
        }),
      );
      toast.success("Authoritative backend simulation completed.");
    },
    onError: (error) => toast.error(readApiError(error, "Simulation failed.")),
  });
  const saveSimulation = useMutation({
    mutationFn: async () => {
      const response = await apiFetch("/simulations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          preview_request: requestPayload,
          target_date: targetDate || today(),
          mtg_minutes_document_id: null,
        }),
      });
      if (!response.ok) await throwApiError(response);
      return (await response.json()) as {
        simulation_id: number;
        status: string;
        document_due_at?: string | null;
      };
    },
    onSuccess: (result) => {
      toast.success(
        `Simulation #${result.simulation_id} reserved. Upload the meeting document within 24 hours.`,
      );
    },
    onError: (error) => toast.error(readApiError(error, "Could not save the simulation.")),
  });

  if (!can("simulation.run")) return <AccessDenied what="running simulations" />;

  function toggleOption(option: SimulationOption) {
    const key = `${option.po_id}::${option.po_line_id}`;
    setPreview(null);
    setPlannerItems((items) => {
      if (items.some((item) => item.id === key)) {
        return items
          .filter((item) => item.id !== key)
          .map((item, index) => ({ ...item, priorityIndex: index + 1 }));
      }
      return [
        ...items,
        {
          id: key,
          poId: String(option.po_id),
          poNumber: option.po_number,
          lineId: String(option.po_line_id),
          fgpn: option.fgpn_code,
          ...(option.description ? { description: option.description } : {}),
          defaultQty: Number(option.outstanding_quantity),
          simQty: Number(option.outstanding_quantity),
          priorityIndex: items.length + 1,
        },
      ];
    });
  }

  function updatePlanner(items: PlannerFgpnItem[]) {
    setPlannerItems(
      items.map(({ coveragePercent: _coverage, launchableQty: _launchable, ...item }) => item),
    );
    setPreview(null);
  }

  function exportPdf() {
    if (!preview || !project) return;
    exportSimulationToPdf({
      ref: `Simulation-${project.project_code}-${today()}`,
      projectName: project.name,
      projectId: String(project.project_id),
      engineerName: user.fullName,
      engineerUsername: user.username,
      runAt: new Date().toISOString(),
      mode: "Order + Manual Entry",
      safetyCoefficient: Number(coefficient),
      includeInTransit: includeTransit,
      ...(targetDate ? { targetDate } : {}),
      feasibility: preview.is_feasible
        ? "Fully feasible"
        : Number(preview.total_launchable_quantity) > 0
          ? "Partially feasible"
          : "Not feasible",
      totalPlannedOutput: Number(preview.total_requested_quantity),
      plannerItems,
      materialBreakdown: preview.material_summaries.map((material) => ({
        partNumber: material.material_part_number,
        description: material.description,
        unit: material.unit,
        bomUsage: 0,
        required: Number(material.total_demand),
        sources: [],
        practical: Number(material.warehouse_stock),
        transit: Number(material.in_transit),
        wip: Number(material.cutman_wip),
        available: Number(material.available_stock),
        shortfall: Number(material.shortfall),
      })),
    });
  }

  return (
    <div className="space-y-4 pb-12">
      <PageHeader
        title="Run & Save Material Simulation"
        subtitle="Select current PO lines, order their priority, edit quantities and let the backend optimize physical stock units globally."
        crumbs={[{ label: "Simulations", to: "/simulations" }, { label: "New simulation" }]}
        meta={
          <>
            <StatusBadge tone="info">Order + Manual Entry</StatusBadge>
            <StatusBadge tone="neutral">Production → Warehouse → Confirmed Transit</StatusBadge>
          </>
        }
        actions={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={!preview} onClick={exportPdf}>
              <FileDown className="size-4" /> Export backend result
            </Button>
            <Button
              size="sm"
              disabled={!preview || saveSimulation.isPending}
              onClick={() => saveSimulation.mutate()}
            >
              <Save className="size-4" /> Reserve simulation
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 p-4 lg:grid-cols-[380px_minmax(0,1fr)]">
        <Section
          title="Current PO lines"
          description="Selections may span several POs in the same project."
        >
          <div className="max-h-[520px] space-y-3 overflow-auto p-3">
            {options.isLoading && (
              <p className="text-xs text-muted-foreground">Loading current PO lines…</p>
            )}
            {options.isError && (
              <p className="text-xs text-danger">
                {readApiError(options.error, "Could not load current PO lines.")}
              </p>
            )}
            {!projectId && <p className="text-xs text-muted-foreground">Select a project first.</p>}
            {groupedOptions.map(([poId, group]) => {
              const isHidden = collapsedPos.has(poId);
              return (
                <div key={poId} className="rounded-md border overflow-hidden">
                  <div
                    className={`flex items-center justify-between bg-muted/50 px-3 py-2 ${
                      !isHidden ? "border-b" : ""
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="font-mono text-xs font-semibold text-foreground truncate">
                        {group.poNumber}
                      </span>
                      <span className="text-[11px] text-muted-foreground font-normal shrink-0">
                        ({group.lines.length} {group.lines.length === 1 ? "line" : "lines"})
                      </span>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleHidePo(poId)}
                      className="h-6 gap-1 px-2 text-xs font-medium text-muted-foreground hover:text-foreground"
                    >
                      {isHidden ? (
                        <>
                          <ChevronRight className="size-3.5" />
                          <span>Show</span>
                        </>
                      ) : (
                        <>
                          <ChevronDown className="size-3.5" />
                          <span>Hide</span>
                        </>
                      )}
                    </Button>
                  </div>
                  {!isHidden &&
                    group.lines.map((line) => {
                      const key = `${line.po_id}::${line.po_line_id}`;
                      return (
                        <label
                          key={key}
                          className="flex cursor-pointer items-start gap-2 border-b p-3 last:border-0 hover:bg-muted/30"
                        >
                          <Checkbox
                            checked={selectedKeys.has(key)}
                            onCheckedChange={() => toggleOption(line)}
                          />
                          <span className="min-w-0">
                            <span className="block font-mono text-xs font-semibold">
                              {line.fgpn_code}
                            </span>
                            <span className="block truncate text-[11px] text-muted-foreground">
                              Outstanding {line.outstanding_quantity} pcs ·{" "}
                              {line.description ?? "Finished good"}
                            </span>
                          </span>
                        </label>
                      );
                    })}
                </div>
              );
            })}
          </div>
        </Section>

        <Section
          title="Simulation parameters"
          description="The target date filters supplier plans; only physically confirmed arrivals may be launched."
        >
          <div className="grid gap-4 p-4 sm:grid-cols-2">
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Project</Label>
              <Select
                value={projectId}
                onValueChange={(value) => {
                  setProjectId(value);
                  setPlannerItems([]);
                  setPreview(null);
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select project" />
                </SelectTrigger>
                <SelectContent>
                  {(projects.data?.items ?? [])
                    .filter((item) => item.status === "Active")
                    .map((item) => (
                      <SelectItem key={item.project_id} value={String(item.project_id)}>
                        {item.project_code} · {item.name}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Safety coefficient</Label>
              <Input
                type="number"
                min="1"
                step="0.01"
                value={coefficient}
                onChange={(event) => {
                  setCoefficient(event.target.value);
                  setPreview(null);
                }}
              />
              <p className="text-[11px] text-muted-foreground">
                Minimum 1. Total sqm is currently interpreted as metres.
              </p>
            </div>
            <div className="space-y-2 rounded-md border p-3">
              <div className="flex items-center justify-between">
                <Label>Restrict to project engineer stock</Label>
                <Switch
                  checked={restrictToOwnStock}
                  onCheckedChange={(checked) => {
                    setRestrictToOwnStock(checked);
                    setPreview(null);
                  }}
                />
              </div>
              {restrictToOwnStock && (
                <div className="flex items-center justify-between">
                  <Label>Include global stock</Label>
                  <Switch
                    checked={includeGlobalStock}
                    onCheckedChange={(checked) => {
                      setIncludeGlobalStock(checked);
                      setPreview(null);
                    }}
                  />
                </div>
              )}
            </div>
            <div className="space-y-2 rounded-md border p-3">
              <div className="flex items-center justify-between">
                <Label>Include supplier ETA stock</Label>
                <Switch
                  checked={includeTransit}
                  onCheckedChange={(checked) => {
                    setIncludeTransit(checked);
                    setPreview(null);
                  }}
                />
              </div>
              <p className="text-[11px] text-muted-foreground">
                Planning only until warehouse confirmation.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label>
                <CalendarDays className="mr-1 inline size-4" /> Target date
              </Label>
              <Input
                type="date"
                disabled={!includeTransit}
                value={targetDate}
                onChange={(event) => {
                  setTargetDate(event.target.value);
                  setPreview(null);
                }}
              />
            </div>
            <div className="flex items-end sm:col-span-2">
              <Button
                className="w-full"
                disabled={!runnable || runPreview.isPending}
                onClick={() => runPreview.mutate()}
              >
                <Play className="size-4" />{" "}
                {runPreview.isPending ? "Optimizing…" : "Run authoritative preview"}
              </Button>
            </div>
          </div>
        </Section>
      </div>

      <div className="px-4">
        {plannerItems.length > 0 ? (
          <SimulationFgpnPlanner items={plannerItems} onItemsChange={updatePlanner} />
        ) : (
          <div className="rounded-md border border-dashed p-6 text-center text-xs text-muted-foreground">
            Select PO/FGPN rows to create the ordered plan.
          </div>
        )}
      </div>

      {preview && (
        <div className="space-y-4 px-4">
          <div
            className={`rounded-lg border p-4 ${preview.is_feasible ? "border-ok/30 bg-ok-soft" : "border-warn/30 bg-warn-soft"}`}
          >
            <div className="flex items-center gap-2">
              {preview.is_feasible ? (
                <CheckCircle2 className="size-5 text-ok" />
              ) : (
                <AlertTriangle className="size-5 text-warn" />
              )}
              <strong>
                {preview.is_feasible
                  ? "All requested quantities are covered"
                  : "Partial launch plan"}
              </strong>
            </div>
            <p className="mt-1 text-sm">
              Requested {preview.total_requested_quantity} pcs · launchable{" "}
              {preview.total_launchable_quantity} pcs.
            </p>
            {preview.suggestion && (
              <p className="mt-1 text-xs text-muted-foreground">{preview.suggestion}</p>
            )}
          </div>
          <Section
            title="Material feasibility"
            description="Demand and coverage returned by the backend optimizer."
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-xs">
                <thead className="bg-muted/60">
                  <tr>
                    <th className="px-3 py-2 text-left">Material</th>
                    <th className="text-right">Demand</th>
                    <th className="text-right">Production</th>
                    <th className="text-right">Warehouse</th>
                    <th className="text-right">Transit</th>
                    <th className="text-right">Allocated</th>
                    <th className="px-3 text-right">Shortfall</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.material_summaries.map((material) => (
                    <tr key={material.material_part_number} className="border-t">
                      <td className="px-3 py-2">
                        <span className="font-mono font-semibold">
                          {material.material_part_number}
                        </span>
                        <span className="ml-2 text-muted-foreground">{material.description}</span>
                      </td>
                      <td className="text-right">
                        {material.total_demand} {material.unit}
                      </td>
                      <td className="text-right">{material.cutman_wip}</td>
                      <td className="text-right">{material.warehouse_stock}</td>
                      <td className="text-right">{includeTransit ? material.in_transit : "—"}</td>
                      <td className="text-right">{material.allocated_quantity}</td>
                      <td className="px-3 text-right font-semibold">{material.shortfall}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
          <Section
            title="Optimized stock-unit selection"
            description="Units are selected globally for the combined demand. Whole rolls show their complete physical issue quantity."
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] text-xs">
                <thead className="bg-muted/60">
                  <tr>
                    <th className="px-3 py-2 text-left">Stock unit</th>
                    <th className="text-left">Material</th>
                    <th className="text-left">Source</th>
                    <th className="text-right">Available</th>
                    <th className="text-right">Physical allocation</th>
                    <th className="px-3 text-right">Remaining</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.allocation_details.map((allocation) => (
                    <tr
                      key={`${allocation.stock_unit_id}-${allocation.material_part_number}`}
                      className="border-t"
                    >
                      <td className="px-3 py-2 font-mono">
                        {allocation.business_unit_id ?? `#${allocation.stock_unit_id}`}{" "}
                        {allocation.is_whole_issue && <StatusBadge tone="info">whole</StatusBadge>}
                      </td>
                      <td className="font-mono">{allocation.material_part_number}</td>
                      <td>{allocation.source}</td>
                      <td className="text-right">{allocation.available_quantity}</td>
                      <td className="text-right font-semibold">{allocation.allocated_quantity}</td>
                      <td className="px-3 text-right">{allocation.remaining_quantity}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        </div>
      )}
    </div>
  );
}
