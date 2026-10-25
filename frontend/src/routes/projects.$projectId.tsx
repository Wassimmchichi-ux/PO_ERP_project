import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { PageHeader, Section, KeyValue } from "@/components/erp/PageHeader";
import { AutoBadge, StatusBadge } from "@/components/erp/StatusBadge";
import { AccessDenied, EmptyState } from "@/components/erp/EmptyState";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useSession } from "@/lib/erp/session";
import {
  auditEvents,
  bomVersions,
  customerDeliveries,
  deliveryInstructions,
  documents,
  poRemaining,
  poQty,
  projects,
  purchaseOrders,
  simulations,
  users,
} from "@/lib/erp/data";
import { fmtDate, fmtDateTime, money, nf } from "@/lib/erp/format";
import { pageTitle } from "@/lib/erp/appInfo";

export const Route = createFileRoute("/projects/$projectId")({
  loader: ({ params }) => {
    const project = projects.find((p) => p.id === params.projectId);
    if (!project) throw notFound();
    return { project };
  },
  head: ({ loaderData }) => {
    if (!loaderData)
      return {
        meta: [{ title: pageTitle("Project unavailable") }, { name: "robots", content: "noindex" }],
      };
    const t = pageTitle(`${loaderData.project.code} ${loaderData.project.name}`);
    const d = `Project workspace for ${loaderData.project.name}: purchase orders, BOM versions, launch operations, handovers and documents.`;
    return {
      meta: [
        { title: t },
        { name: "description", content: d },
        { property: "og:title", content: t },
        { property: "og:description", content: d },
      ],
    };
  },
  component: ProjectDetail,
});

function ProjectDetail() {
  const { project } = Route.useLoaderData();
  const { can, projectIds, canWrite } = useSession();

  if (!can("project.view")) return <AccessDenied what="project records" />;
  if (!projectIds.includes(project.id))
    return <AccessDenied what={`project ${project.code}, which is not assigned to you`} />;

  const pos = purchaseOrders.filter((p) => p.projectId === project.id);
  const boms = bomVersions.filter((b) => b.projectId === project.id);
  const sims = simulations.filter((s) => s.projectId === project.id);
  const dis = deliveryInstructions.filter((d) => d.projectId === project.id);
  const cds = customerDeliveries.filter((d) => d.projectId === project.id);
  const docs = documents.filter((d) => d.projectId === project.id);
  const events = auditEvents.filter((e) => e.projectId === project.id);

  return (
    <>
      <PageHeader
        title={`${project.code} · ${project.name}`}
        subtitle={`${project.customer} · ${project.carModel ?? "no car model recorded"}`}
        crumbs={[{ label: "Projects", to: "/projects" }, { label: project.code }]}
        meta={
          <>
            <AutoBadge value={project.status} />
            <StatusBadge tone={canWrite(project.id) ? "info" : "neutral"}>
              {canWrite(project.id) ? "Write access" : "Read-only"}
            </StatusBadge>
          </>
        }
      />
      <div className="space-y-4 p-4">
        <Section title="Project record">
          <KeyValue
            items={[
              { label: "Project code", value: <span className="num">{project.code}</span> },
              { label: "JIT customer", value: project.customer },
              { label: "Car model", value: project.carModel ?? "—" },
              { label: "Created", value: fmtDate(project.createdAt) },
              {
                label: "Responsible users",
                value:
                  project.responsibleUserIds
                    .map((id) => users.find((u) => u.id === id)?.fullName ?? id)
                    .join(", ") || "—",
              },
              {
                label: "Purchase orders",
                value: `${pos.length} (${pos.filter((p) => p.status !== "Delivered").length} open)`,
              },
              {
                label: "Active BOM",
                value: boms.find((b) => b.active)?.fileName ?? "No BOM uploaded",
              },
              {
                label: "Launch operations",
                value: `${sims.filter((s) => s.approved).length} approved`,
              },
            ]}
          />
        </Section>

        <Tabs defaultValue="pos">
          <TabsList>
            <TabsTrigger value="pos">Purchase orders</TabsTrigger>
            <TabsTrigger value="launch">Launch &amp; handover</TabsTrigger>
            <TabsTrigger value="deliveries">Customer deliveries</TabsTrigger>
            <TabsTrigger value="docs">Documents</TabsTrigger>
            <TabsTrigger value="audit">Project history</TabsTrigger>
          </TabsList>

          <TabsContent value="pos">
            <Section>
              {pos.length === 0 ? (
                <EmptyState
                  title="No purchase order for this project"
                  description="Purchase orders enter the system through PO Intake as PDF documents."
                />
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-muted/60">
                      <th className="label-caps px-4 py-2 text-left">PO number</th>
                      <th className="label-caps px-4 py-2 text-left">Version</th>
                      <th className="label-caps px-4 py-2 text-right">Ordered</th>
                      <th className="label-caps px-4 py-2 text-right">Remaining</th>
                      <th className="label-caps px-4 py-2 text-left">Delivery week</th>
                      <th className="label-caps px-4 py-2 text-left">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pos.map((p) => (
                      <tr key={p.id} className="border-b border-border last:border-0">
                        <td className="px-4 py-1.5">
                          <Link
                            to="/purchase-orders/$poId"
                            params={{ poId: p.id }}
                            className="num text-info hover:underline"
                          >
                            {p.poNumber}
                          </Link>
                        </td>
                        <td className="num px-4 py-1.5">V{p.currentVersion}</td>
                        <td className="num px-4 py-1.5 text-right">{nf.format(poQty(p))}</td>
                        <td className="num px-4 py-1.5 text-right">{nf.format(poRemaining(p))}</td>
                        <td className="num px-4 py-1.5">{p.deliveryWeek}</td>
                        <td className="px-4 py-1.5">
                          <AutoBadge value={p.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Section>
          </TabsContent>

          <TabsContent value="launch">
            <div className="grid gap-4 xl:grid-cols-2">
              <Section title="Launch simulations">
                {sims.length === 0 ? (
                  <EmptyState title="No simulation run for this project" />
                ) : (
                  <div className="divide-y divide-border">
                    {sims.map((s) => (
                      <Link
                        key={s.id}
                        to="/simulations/$simId"
                        params={{ simId: s.id }}
                        className="flex items-center justify-between gap-3 px-4 py-2 hover:bg-muted"
                      >
                        <div>
                          <p className="num text-[13px]">{s.ref}</p>
                          <p className="text-xs text-muted-foreground">
                            {s.mode} · {fmtDateTime(s.runAt)} · {s.runBy}
                          </p>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <AutoBadge value={s.feasibility} />
                          {s.approved ? (
                            <StatusBadge tone="ok">Approved</StatusBadge>
                          ) : (
                            <StatusBadge tone="warn">Not approved</StatusBadge>
                          )}
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </Section>
              <Section title="Warehouse-to-manufacturing handovers">
                {dis.length === 0 ? (
                  <EmptyState title="No delivery instruction issued" />
                ) : (
                  <div className="divide-y divide-border">
                    {dis.map((d) => (
                      <div key={d.id} className="flex items-center justify-between gap-3 px-4 py-2">
                        <div>
                          <p className="num text-[13px]">{d.ref}</p>
                          <p className="text-xs text-muted-foreground">
                            Required {fmtDateTime(d.requiredAt)} · {d.items.length} item(s)
                          </p>
                        </div>
                        <AutoBadge value={d.status} />
                      </div>
                    ))}
                  </div>
                )}
              </Section>
            </div>
          </TabsContent>

          <TabsContent value="deliveries">
            <Section>
              {cds.length === 0 ? (
                <EmptyState title="No customer delivery recorded" />
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-muted/60">
                      <th className="label-caps px-4 py-2 text-left">Reference</th>
                      <th className="label-caps px-4 py-2 text-left">FGPN</th>
                      <th className="label-caps px-4 py-2 text-right">Quantity</th>
                      <th className="label-caps px-4 py-2 text-right">Value</th>
                      <th className="label-caps px-4 py-2 text-left">Method</th>
                      <th className="label-caps px-4 py-2 text-left">Date</th>
                      <th className="label-caps px-4 py-2 text-left">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cds.map((d) => (
                      <tr key={d.id} className="border-b border-border last:border-0">
                        <td className="num px-4 py-1.5">{d.ref}</td>
                        <td className="num px-4 py-1.5">{d.fgpn}</td>
                        <td className="num px-4 py-1.5 text-right">{nf.format(d.quantity)}</td>
                        <td className="num px-4 py-1.5 text-right">
                          {money(d.quantity * d.unitPrice)}
                        </td>
                        <td className="px-4 py-1.5 text-xs">{d.deliveryMethod}</td>
                        <td className="num px-4 py-1.5">{fmtDate(d.deliveryDate)}</td>
                        <td className="px-4 py-1.5">
                          <AutoBadge value={d.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Section>
          </TabsContent>

          <TabsContent value="docs">
            <Section
              title="Linked documents"
              description="Managed centrally in the Documents module and linked to this project."
              actions={
                <Link to="/documents" className="text-xs text-info hover:underline">
                  Open document register
                </Link>
              }
            >
              {docs.length === 0 ? (
                <EmptyState title="No document linked to this project" />
              ) : (
                <div className="divide-y divide-border">
                  {docs.map((d) => (
                    <div key={d.id} className="flex items-center justify-between gap-3 px-4 py-2">
                      <div className="min-w-0">
                        <p className="truncate text-[13px] font-medium">{d.fileName}</p>
                        <p className="text-xs text-muted-foreground">
                          {d.type} · v{d.version} · {fmtDateTime(d.uploadedAt)} · {d.uploadedBy}
                        </p>
                      </div>
                      <StatusBadge tone={d.draft ? "warn" : "neutral"} dot={false}>
                        {d.linkedEntity.ref}
                      </StatusBadge>
                    </div>
                  ))}
                </div>
              )}
            </Section>
          </TabsContent>

          <TabsContent value="audit">
            <Section
              title="Project traceability"
              description="Immutable events recorded for this project."
            >
              {events.length === 0 ? (
                <EmptyState title="No recorded event" />
              ) : (
                <div className="divide-y divide-border">
                  {events.map((e) => (
                    <div key={e.id} className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <StatusBadge tone="neutral" dot={false}>
                          {e.category}
                        </StatusBadge>
                        <span className="text-[13px] font-medium">{e.event}</span>
                        <span className="num ml-auto text-xs text-muted-foreground">
                          {fmtDateTime(e.at)} · {e.by}
                        </span>
                      </div>
                      <p className="mt-0.5 text-xs text-muted-foreground">{e.detail}</p>
                    </div>
                  ))}
                </div>
              )}
            </Section>
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
}
