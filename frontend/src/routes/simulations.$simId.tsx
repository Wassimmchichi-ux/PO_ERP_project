import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useState } from "react";
import { AlertTriangle, FileDown, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { PageHeader, Section, KeyValue } from "@/components/erp/PageHeader";
import { AutoBadge, StatusBadge } from "@/components/erp/StatusBadge";
import { AccessDenied } from "@/components/erp/EmptyState";
import { ConfirmDialog } from "@/components/erp/ConfirmDialog";
import { FileDropzone } from "@/components/erp/FileDropzone";
import { Button } from "@/components/ui/button";
import { useSession } from "@/lib/erp/session";
import { bomVersions, documents, findPo, projectLabel, simulations } from "@/lib/erp/data";
import { fmtDateTime, nf } from "@/lib/erp/format";
import { pageTitle } from "@/lib/erp/appInfo";

export const Route = createFileRoute("/simulations/$simId")({
  loader: ({ params }) => {
    const sim = simulations.find((s) => s.id === params.simId);
    if (!sim) throw notFound();
    return { sim };
  },
  head: ({ loaderData }) => {
    if (!loaderData)
      return {
        meta: [
          { title: pageTitle("Simulation unavailable") },
          { name: "robots", content: "noindex" },
        ],
      };
    const t = pageTitle(`${loaderData.sim.ref} - Simulation Result`);
    const d = `Feasibility result ${loaderData.sim.feasibility} with material requirements, shortfalls and launch decision for simulation ${loaderData.sim.ref}.`;
    return {
      meta: [
        { title: t },
        { name: "description", content: d },
        { property: "og:title", content: t },
        { property: "og:description", content: d },
      ],
    };
  },
  component: SimulationDetail,
});

function SimulationDetail() {
  const { sim } = Route.useLoaderData();
  const { can, canWrite, projectIds } = useSession();
  const [approveOpen, setApproveOpen] = useState(false);
  const [pv, setPv] = useState<string | null>(
    sim.meetingMinutesDocId
      ? (documents.find((d) => d.id === sim.meetingMinutesDocId)?.fileName ?? null)
      : null,
  );

  if (!can("simulation.view")) return <AccessDenied what="simulation results" />;
  if (!projectIds.includes(sim.projectId))
    return <AccessDenied what={`simulations of project ${projectLabel(sim.projectId)}`} />;

  const bom = bomVersions.find((b) => b.id === sim.bomVersionId);
  const short = sim.requirements.filter((r) => r.shortfall > 0);
  const canApprove = can("simulation.run") && canWrite(sim.projectId);

  const totals = sim.requirements.reduce(
    (a, r) => ({
      required: a.required + r.requiredQty,
      practical: a.practical + r.practicalStock,
      wip: a.wip + r.wipAvailable,
      incoming: a.incoming + r.plannedIncoming,
      shortfall: a.shortfall + r.shortfall,
    }),
    { required: 0, practical: 0, wip: 0, incoming: 0, shortfall: 0 },
  );

  return (
    <>
      <PageHeader
        title={`Simulation ${sim.ref}`}
        subtitle={`${sim.mode} · run ${fmtDateTime(sim.runAt)} by ${sim.runBy} · simulations never modify stock`}
        crumbs={[{ label: "Simulations", to: "/simulations" }, { label: sim.ref }]}
        meta={
          <>
            <AutoBadge value={sim.feasibility} />
            <StatusBadge tone="neutral">Safety coefficient ×{sim.safetyCoefficient}</StatusBadge>
            <StatusBadge tone={sim.includeFutureStock ? "info" : "neutral"}>
              {sim.includeFutureStock ? "Future stock included" : "Current stock only"}
            </StatusBadge>
            {sim.approved ? (
              <StatusBadge tone="ok">
                Launch approved {fmtDateTime(sim.approvedAt)} by {sim.approvedBy}
              </StatusBadge>
            ) : (
              <StatusBadge tone="warn">Launch decision pending</StatusBadge>
            )}
          </>
        }
        actions={
          <>
            <Button variant="outline" size="sm" className="h-8">
              <FileDown className="size-3.5" /> Export simulation draft
            </Button>
            {canApprove && !sim.approved && (
              <Button size="sm" className="h-8" disabled={!pv} onClick={() => setApproveOpen(true)}>
                <ShieldCheck className="size-3.5" /> Approve launch
              </Button>
            )}
          </>
        }
      />

      <div className="space-y-4 p-4">
        {sim.feasibility !== "Fully feasible" && (
          <div className="panel flex items-start gap-3 border-l-4 border-l-danger p-4">
            <AlertTriangle className="mt-0.5 size-5 shrink-0 text-danger" />
            <div>
              <p className="text-sm font-semibold">
                {short.length} material(s) below the required quantity
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {sim.maxLaunchableQty !== undefined
                  ? `With the material currently under ERP responsibility, at most ${nf.format(sim.maxLaunchableQty)} finished pieces can be launched. `
                  : ""}
                Requirements use the active bill of materials multiplied by the safety coefficient ×
                {sim.safetyCoefficient}.
              </p>
            </div>
          </div>
        )}

        <Section title="Simulation parameters">
          <KeyValue
            items={[
              { label: "Project", value: projectLabel(sim.projectId) },
              { label: "Mode", value: sim.mode },
              {
                label: "Purchase orders",
                value: (
                  <span className="flex flex-wrap gap-2">
                    {sim.poIds.length === 0
                      ? "—"
                      : sim.poIds.map((id) => {
                          const po = findPo(id);
                          return po ? (
                            <Link
                              key={id}
                              to="/purchase-orders/$poId"
                              params={{ poId: id }}
                              className="num text-info hover:underline"
                            >
                              {po.poNumber}
                            </Link>
                          ) : null;
                        })}
                  </span>
                ),
              },
              { label: "BOM version", value: bom ? `V${bom.version} — ${bom.fileName}` : "—" },
              { label: "Safety coefficient", value: `×${sim.safetyCoefficient}` },
              { label: "Target date", value: sim.targetDate ?? "—" },
              {
                label: "Future stock",
                value: sim.includeFutureStock
                  ? "Planned incoming quantities counted"
                  : "Warehouse stock only",
              },
              { label: "Run by", value: `${sim.runBy} — ${fmtDateTime(sim.runAt)}` },
            ]}
          />
        </Section>

        <Section
          title="Material requirements"
          description="ERP-managed stock (warehouse and in-transit) is separated from cutting-area quantities reported by CutMan."
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/60">
                <th className="label-caps px-4 py-2 text-left">Material</th>
                <th className="label-caps px-4 py-2 text-left">Description</th>
                <th className="label-caps px-4 py-2 text-right">BOM usage</th>
                <th className="label-caps px-4 py-2 text-right">Required (×coef.)</th>
                <th className="label-caps px-4 py-2 text-right">Warehouse stock</th>
                <th className="label-caps px-4 py-2 text-right">CutMan area</th>
                <th className="label-caps px-4 py-2 text-right">Planned incoming</th>
                <th className="label-caps px-4 py-2 text-right">Shortfall</th>
                <th className="label-caps px-4 py-2 text-left">Result</th>
              </tr>
            </thead>
            <tbody>
              {sim.requirements.map((r) => (
                <tr
                  key={r.materialPartNumber}
                  className={`border-b border-border last:border-0 ${r.shortfall > 0 ? "bg-danger-soft/40" : ""}`}
                >
                  <td className="num px-4 py-1.5">{r.materialPartNumber}</td>
                  <td className="px-4 py-1.5 text-xs">{r.description}</td>
                  <td className="num px-4 py-1.5 text-right">
                    {nf.format(r.bomUsage)} {r.unit}
                  </td>
                  <td className="num px-4 py-1.5 text-right font-semibold">
                    {nf.format(r.requiredQty)} {r.unit}
                  </td>
                  <td className="num px-4 py-1.5 text-right">{nf.format(r.practicalStock)}</td>
                  <td className="num px-4 py-1.5 text-right text-muted-foreground">
                    {nf.format(r.wipAvailable)}
                  </td>
                  <td className="num px-4 py-1.5 text-right">
                    {sim.includeFutureStock ? nf.format(r.plannedIncoming) : "not counted"}
                  </td>
                  <td className="num px-4 py-1.5 text-right font-semibold text-danger">
                    {r.shortfall > 0 ? nf.format(r.shortfall) : "—"}
                  </td>
                  <td className="px-4 py-1.5">
                    {r.shortfall > 0 ? (
                      <StatusBadge tone="danger">Insufficient</StatusBadge>
                    ) : (
                      <StatusBadge tone="ok">Covered</StatusBadge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-border bg-muted/60 font-semibold">
                <td className="px-4 py-2" colSpan={3}>
                  Totals
                </td>
                <td className="num px-4 py-2 text-right">{nf.format(totals.required)}</td>
                <td className="num px-4 py-2 text-right">{nf.format(totals.practical)}</td>
                <td className="num px-4 py-2 text-right">{nf.format(totals.wip)}</td>
                <td className="num px-4 py-2 text-right">{nf.format(totals.incoming)}</td>
                <td className="num px-4 py-2 text-right text-danger">
                  {nf.format(totals.shortfall)}
                </td>
                <td />
              </tr>
            </tfoot>
          </table>
        </Section>

        <Section
          title="Launch decision"
          description="A launch can only be approved once the signed meeting minutes (PV) are attached."
        >
          <div className="grid gap-4 p-4 md:grid-cols-2">
            <FileDropzone
              accept={[".pdf"]}
              label={pv ?? "Attach signed meeting minutes (PV)"}
              hint="PDF only. The PV is stored in the central document register and linked to this simulation."
              rejectMessage="Meeting minutes must be provided as a PDF."
              disabled={sim.approved || !canApprove}
              onAccepted={setPv}
            />
            <ul className="space-y-2 text-xs text-muted-foreground">
              <li>
                Feasibility result: <strong className="text-foreground">{sim.feasibility}</strong>
              </li>
              <li>
                Meeting minutes: <strong className="text-foreground">{pv ?? "not attached"}</strong>
              </li>
              <li>
                Approval:{" "}
                <strong className="text-foreground">
                  {sim.approved
                    ? `granted ${fmtDateTime(sim.approvedAt)} by ${sim.approvedBy}`
                    : canApprove
                      ? "pending your decision"
                      : "reserved to the launch decision role"}
                </strong>
              </li>
              <li>
                Approving a partially feasible simulation launches only the confirmed launchable
                quantity; the remaining demand stays open.
              </li>
            </ul>
          </div>
        </Section>
      </div>

      <ConfirmDialog
        open={approveOpen}
        onOpenChange={setApproveOpen}
        title="Approve launch decision"
        confirmLabel="Approve launch"
        description={
          <>
            The simulation result <strong>{sim.feasibility}</strong> and the attached meeting
            minutes will be recorded as the launch decision for {sim.ref}. The decision is traceable
            to your user account and cannot be edited afterwards.
          </>
        }
        onConfirm={() => {
          setApproveOpen(false);
          toast.success(`Launch approved for ${sim.ref}. Decision recorded in the audit trail.`);
        }}
      />
    </>
  );
}
