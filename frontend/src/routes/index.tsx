import { createFileRoute, Link } from "@tanstack/react-router";
import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  ClipboardList,
  FileWarning,
  FlaskConical,
  PackageCheck,
  Truck,
} from "lucide-react";
import { PageHeader, Section } from "@/components/erp/PageHeader";
import { AutoBadge, StatusBadge } from "@/components/erp/StatusBadge";
import { EmptyState, AccessDenied } from "@/components/erp/EmptyState";
import { useProjectScope, useSession } from "@/lib/erp/session";
import {
  customerDeliveries,
  deliveryInstructions,
  documents,
  isBelowThreshold,
  materials,
  poRemaining,
  projectLabel,
  purchaseOrders,
  simulations,
  theoreticalStock,
} from "@/lib/erp/data";
import { fmtDate, fmtDateTime, nf } from "@/lib/erp/format";
import { pageTitle } from "@/lib/erp/appInfo";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: pageTitle("Operations Dashboard") },
      {
        name: "description",
        content:
          "Exception-based launch operations dashboard: critical material alerts, overdue handover documents, pending customer deliveries and launches missing meeting minutes.",
      },
      { property: "og:title", content: pageTitle("Operations Dashboard") },
      {
        property: "og:description",
        content:
          "Monitor purchase orders, material stock, launch simulations, warehouse handovers and deliveries in one industrial ERP workspace.",
      },
    ],
  }),
  component: Dashboard,
});

function Panel({
  title,
  hint,
  icon: Icon,
  tone,
  to,
  children,
}: {
  title: string;
  hint: string;
  icon: typeof Boxes;
  tone: "danger" | "warn" | "info" | "neutral";
  to: string;
  children: React.ReactNode;
}) {
  const border =
    tone === "danger"
      ? "border-l-danger"
      : tone === "warn"
        ? "border-l-warn"
        : tone === "info"
          ? "border-l-info"
          : "border-l-border";
  return (
    <section className={`panel overflow-hidden border-l-4 ${border}`}>
      <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Icon className="size-4 text-muted-foreground" />
          <div>
            <h2 className="text-sm font-semibold">{title}</h2>
            <p className="text-xs text-muted-foreground">{hint}</p>
          </div>
        </div>
        <Link
          to={to}
          className="flex items-center gap-1 text-xs font-medium text-info hover:underline"
        >
          Open <ArrowRight className="size-3" />
        </Link>
      </header>
      {children}
    </section>
  );
}

function Row({
  primary,
  secondary,
  right,
}: {
  primary: React.ReactNode;
  secondary: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-2 last:border-0">
      <div className="min-w-0">
        <p className="truncate text-[13px] font-medium text-foreground">{primary}</p>
        <p className="truncate text-xs text-muted-foreground">{secondary}</p>
      </div>
      {right}
    </div>
  );
}

function Dashboard() {
  const { can, user } = useSession();
  const scope = useProjectScope();

  if (!can("dashboard.all") && !can("dashboard.own")) {
    return <RoleLanding />;
  }

  const criticalMaterials = materials.filter(isBelowThreshold);
  const overdueHandovers = deliveryInstructions.filter(
    (d) => d.status === "Awaiting validation" && scope.inScope(d.projectId),
  );
  const pendingCustomer = customerDeliveries.filter(
    (d) => d.status === "Pending confirmation" && scope.inScope(d.projectId),
  );
  const orphanLaunches = simulations.filter(
    (s) => !s.approved && !s.meetingMinutesDocId && scope.inScope(s.projectId),
  );
  const activePos = purchaseOrders.filter(
    (p) => p.status !== "Delivered" && scope.inScope(p.projectId),
  );
  const readOnly = !can("project.write");

  return (
    <>
      <PageHeader
        title="Operations dashboard"
        subtitle={`Exception centre for ${user.fullName} · items requiring action are listed first`}
        meta={
          <>
            <StatusBadge tone={criticalMaterials.length ? "danger" : "ok"}>
              {criticalMaterials.length} material alerts
            </StatusBadge>
            <StatusBadge tone={overdueHandovers.length ? "warn" : "ok"}>
              {overdueHandovers.length} handovers to validate
            </StatusBadge>
            <StatusBadge tone={pendingCustomer.length ? "warn" : "ok"}>
              {pendingCustomer.length} deliveries awaiting confirmation
            </StatusBadge>
            {readOnly && <StatusBadge tone="neutral">Read-only session</StatusBadge>}
          </>
        }
      />

      <div className="space-y-4 p-4">
        <div className="grid gap-4 xl:grid-cols-2">
          <Panel
            title="Critical material alerts"
            hint="Practical stock at or below the defined critical threshold"
            icon={AlertTriangle}
            tone="danger"
            to="/stock"
          >
            {criticalMaterials.length === 0 ? (
              <EmptyState title="No material below threshold" />
            ) : (
              criticalMaterials.map((m) => (
                <Row
                  key={m.id}
                  primary={
                    <>
                      <span className="num">{m.partNumber}</span> — {m.description}
                    </>
                  }
                  secondary={`Practical ${nf.format(m.practicalStock)} ${m.unit} · threshold ${nf.format(
                    m.criticalThreshold,
                  )} ${m.unit} · theoretical ${nf.format(theoreticalStock(m))} ${m.unit}`}
                  right={<StatusBadge tone="danger">Below threshold</StatusBadge>}
                />
              ))
            )}
          </Panel>

          <Panel
            title="Handover documents awaiting validation"
            hint="Signed warehouse-to-manufacturing scans not yet validated"
            icon={PackageCheck}
            tone="warn"
            to="/handover"
          >
            {overdueHandovers.length === 0 ? (
              <EmptyState title="No handover awaiting validation" />
            ) : (
              overdueHandovers.map((d) => {
                const doc = documents.find((x) => x.id === d.signedDocId);
                return (
                  <Row
                    key={d.id}
                    primary={`${d.ref} — ${projectLabel(d.projectId)}`}
                    secondary={`Receiver ${d.receiverName} · uploaded ${fmtDateTime(doc?.uploadedAt)}`}
                    right={<AutoBadge value={d.status} />}
                  />
                );
              })
            )}
          </Panel>

          <Panel
            title="Customer deliveries pending confirmation"
            hint="Delivered goods without recorded confirmation evidence"
            icon={Truck}
            tone="warn"
            to="/customer-deliveries"
          >
            {pendingCustomer.length === 0 ? (
              <EmptyState title="All deliveries confirmed" />
            ) : (
              pendingCustomer.map((d) => (
                <Row
                  key={d.id}
                  primary={`${d.ref} — ${d.fgpn}`}
                  secondary={`${nf.format(d.quantity)} pcs · ${d.deliveryMethod} · shipped ${fmtDate(
                    d.deliveryDate,
                  )}`}
                  right={<AutoBadge value={d.status} />}
                />
              ))
            )}
          </Panel>

          <Panel
            title="Launches blocked without meeting minutes"
            hint="Completed simulations that cannot be finalised until a PV is linked"
            icon={FileWarning}
            tone="warn"
            to="/simulations"
          >
            {orphanLaunches.length === 0 ? (
              <EmptyState title="No launch waiting on meeting minutes" />
            ) : (
              orphanLaunches.map((s) => (
                <Row
                  key={s.id}
                  primary={`${s.ref} — ${projectLabel(s.projectId)}`}
                  secondary={`${s.mode} · run ${fmtDateTime(s.runAt)} by ${s.runBy}`}
                  right={<AutoBadge value={s.feasibility} />}
                />
              ))
            )}
          </Panel>
        </div>

        <div className="grid gap-4 xl:grid-cols-3">
          <Section
            title="Active purchase orders"
            description="Status, remaining quantity and delivery week"
            className="xl:col-span-2"
          >
            {activePos.length === 0 ? (
              <EmptyState title="No active purchase order in scope" />
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/60">
                    <th className="label-caps px-4 py-2 text-left">PO number</th>
                    <th className="label-caps px-4 py-2 text-left">Project</th>
                    <th className="label-caps px-4 py-2 text-right">Remaining</th>
                    <th className="label-caps px-4 py-2 text-left">Delivery week</th>
                    <th className="label-caps px-4 py-2 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {activePos.map((p) => (
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
                      <td className="px-4 py-1.5 text-xs text-muted-foreground">
                        {projectLabel(p.projectId)}
                      </td>
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

          <Section title="Stock position" description="ERP-managed vs. CutMan production area">
            <div className="divide-y divide-border">
              {materials
                .filter((m) => m.status === "Active")
                .slice(0, 6)
                .map((m) => (
                  <div key={m.id} className="px-4 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="num">{m.partNumber}</span>
                      {isBelowThreshold(m) && <StatusBadge tone="danger">Critical</StatusBadge>}
                    </div>
                    <div className="mt-1 grid grid-cols-3 gap-2 text-[11px]">
                      <div>
                        <span className="label-caps block">Practical</span>
                        <span className="num">{nf.format(m.practicalStock)}</span>
                      </div>
                      <div>
                        <span className="label-caps block">In transit</span>
                        <span className="num text-muted-foreground">
                          {nf.format(m.transitStock)}
                        </span>
                      </div>
                      <div>
                        <span className="label-caps block">WIP (CutMan)</span>
                        <span className="num text-info">{nf.format(m.wipStock)}</span>
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          </Section>
        </div>
      </div>
    </>
  );
}

/** Warehouse and administrator roles land on their own operational entry points. */
function RoleLanding() {
  const { can, user } = useSession();
  const tiles: { to: string; title: string; description: string; icon: typeof Boxes }[] = [];
  if (can("stock.reception.write"))
    tiles.push({
      to: "/stock/reception",
      title: "Stock reception",
      description: "Search a material part number and record received rolls or units.",
      icon: Boxes,
    });
  if (can("handover.code.access"))
    tiles.push({
      to: "/handover/access",
      title: "Delivery code access",
      description: "Enter the 6-digit delivery code to open the delivery instruction.",
      icon: PackageCheck,
    });
  if (can("stock.monitor"))
    tiles.push({
      to: "/stock",
      title: "Stock monitoring",
      description: "Practical, transit and CutMan WIP quantities per material.",
      icon: ClipboardList,
    });
  if (can("admin.users"))
    tiles.push({
      to: "/admin/users",
      title: "Users and access",
      description: "Accounts, role assignment, project assignment and account locks.",
      icon: FlaskConical,
    });
  if (can("admin.reference"))
    tiles.push({
      to: "/admin/reference-lists",
      title: "Reference lists",
      description: "Customers, contacts, FGPNs, receivers, delivery methods, material types.",
      icon: ClipboardList,
    });

  if (tiles.length === 0) return <AccessDenied what="any operational module" />;

  return (
    <>
      <PageHeader
        title={`Welcome, ${user.fullName}`}
        subtitle="Your role gives access to the operations below."
      />
      <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-3">
        {tiles.map((t) => (
          <Link key={t.to} to={t.to} className="panel block p-4 transition-colors hover:bg-muted">
            <t.icon className="mb-2 size-5 text-muted-foreground" />
            <p className="text-sm font-semibold">{t.title}</p>
            <p className="mt-1 text-xs text-muted-foreground">{t.description}</p>
          </Link>
        ))}
      </div>
    </>
  );
}
