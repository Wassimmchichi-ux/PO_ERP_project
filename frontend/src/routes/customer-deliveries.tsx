import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, Eye, FileCheck2, Truck } from "lucide-react";
import { PageHeader, Section } from "@/components/erp/PageHeader";
import { DataTable, type Column } from "@/components/erp/DataTable";
import { AutoBadge, StatusBadge } from "@/components/erp/StatusBadge";
import { AccessDenied } from "@/components/erp/EmptyState";
import { ConfirmDialog } from "@/components/erp/ConfirmDialog";
import { FileDropzone } from "@/components/erp/FileDropzone";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useProjectScope, useSession } from "@/lib/erp/session";
import {
  customerDeliveries,
  deliveryMethods,
  findPo,
  projectLabel,
  resolveProjectId,
  simulations,
} from "@/lib/erp/data";
import { fmtDate, money, nf } from "@/lib/erp/format";
import type { CustomerDelivery } from "@/lib/erp/types";
import { pageTitle } from "@/lib/erp/appInfo";
import { apiFetch, readApiError, throwApiError } from "@/lib/erp/api";

export const Route = createFileRoute("/customer-deliveries")({
  head: () => ({
    meta: [
      { title: pageTitle("Customer Deliveries") },
      {
        name: "description",
        content:
          "Planned, pending and confirmed finished-goods deliveries to JIT customers with quantities, transport method, cost and delivery confirmation.",
      },
      { property: "og:title", content: pageTitle("Customer Deliveries") },
      {
        property: "og:description",
        content: "Track shipments against purchase orders until customer confirmation.",
      },
    ],
  }),
  component: CustomerDeliveriesPage,
});

function CustomerDeliveriesPage() {
  const { can, canWrite, user } = useSession();
  const scope = useProjectScope();
  const [status, setStatus] = useState("all");
  const [target, setTarget] = useState<CustomerDelivery | null>(null);
  const [person, setPerson] = useState("");
  const [method, setMethod] = useState(deliveryMethods[0]?.name ?? "Truck");
  const [date, setDate] = useState("");
  const [launches, setLaunches] = useState<LaunchDeliveryOption[]>([]);
  const [selectedLaunchId, setSelectedLaunchId] = useState("");
  const [deliveryQty, setDeliveryQty] = useState<Record<string, string>>({});
  const [cmrFile, setCmrFile] = useState<File | null>(null);
  const [cmrPreviewUrl, setCmrPreviewUrl] = useState<string | null>(null);
  const [cmrPreviewOpen, setCmrPreviewOpen] = useState(false);
  const [confirmLaunchOpen, setConfirmLaunchOpen] = useState(false);
  const [submittingLaunch, setSubmittingLaunch] = useState(false);

  useEffect(() => {
    let alive = true;
    apiFetch("/customer-deliveries/launches")
      .then(async (response) => {
        if (!response.ok) await throwApiError(response);
        return response.json();
      })
      .then((payload) => {
        if (!alive) return;
        const apiLaunches = (payload.items ?? []).map(mapApiLaunchDelivery);
        setLaunches(apiLaunches.length ? apiLaunches : deriveDemoLaunches());
      })
      .catch(() => {
        if (alive) setLaunches(deriveDemoLaunches());
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!cmrFile) {
      setCmrPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(cmrFile);
    setCmrPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [cmrFile]);

  const rows = customerDeliveries
    .filter((d) => scope.inScope(d.projectId))
    .filter((d) => status === "all" || d.status === status);
  const scopedLaunches = launches.filter((launch) => scope.inScope(launch.projectId));
  const selectedLaunch =
    scopedLaunches.find((launch) => launch.id === selectedLaunchId) ?? scopedLaunches[0];
  const selectedDeliveryLines = useMemo(
    () =>
      selectedLaunch?.lines
        .map((line) => ({
          ...line,
          entered: Number(deliveryQty[line.id] || 0),
        }))
        .filter((line) => line.entered > 0) ?? [],
    [deliveryQty, selectedLaunch],
  );
  const selectedTotalQty = selectedDeliveryLines.reduce((sum, line) => sum + line.entered, 0);
  const selectedCanWrite = selectedLaunch ? canWrite(selectedLaunch.projectId) : false;

  if (!can("customer.delivery.view")) return <AccessDenied what="customer deliveries" />;

  const pending = rows.filter((d) => d.status === "Pending confirmation");
  const planned = rows.filter((d) => d.status === "Planned");
  const totalValue = rows.reduce((s, d) => s + d.quantity * d.unitPrice + d.transportCost, 0);

  const columns: Column<CustomerDelivery>[] = [
    { key: "ref", header: "Reference", mono: true, cell: (d) => d.ref, sortValue: (d) => d.ref },
    {
      key: "po",
      header: "Purchase order",
      mono: true,
      cell: (d) => findPo(d.poId)?.poNumber ?? "—",
    },
    {
      key: "fgpn",
      header: "Finished good",
      cell: (d) => (
        <span>
          <span className="num font-medium">{d.fgpn}</span>
          <span className="ml-2 text-xs text-muted-foreground">{d.description}</span>
        </span>
      ),
    },
    {
      key: "qty",
      header: "Qty",
      align: "right",
      mono: true,
      cell: (d) => nf.format(d.quantity),
      sortValue: (d) => d.quantity,
    },
    {
      key: "value",
      header: "Goods value",
      align: "right",
      mono: true,
      cell: (d) => money(d.quantity * d.unitPrice),
      sortValue: (d) => d.quantity * d.unitPrice,
    },
    {
      key: "transport",
      header: "Transport",
      cell: (d) => (
        <span className="text-xs">
          {d.deliveryMethod} · <span className="num">{money(d.transportCost)}</span>
        </span>
      ),
    },
    {
      key: "date",
      header: "Delivery date",
      mono: true,
      cell: (d) => `${fmtDate(d.deliveryDate)} · ${d.deliveryWeek}`,
      sortValue: (d) => d.deliveryDate,
    },
    {
      key: "project",
      header: "Project",
      cell: (d) => <span className="text-xs">{projectLabel(d.projectId)}</span>,
    },
    {
      key: "status",
      header: "Status",
      cell: (d) => (
        <div className="space-y-1">
          <AutoBadge value={d.status} />
          {d.confirmation && (
            <div className="text-[11px] text-muted-foreground">
              {d.confirmation.method} · {d.confirmation.person}
            </div>
          )}
        </div>
      ),
      sortValue: (d) => d.status,
    },
    {
      key: "actions",
      header: "",
      align: "right",
      cell: (d) =>
        can("customer.delivery.write") &&
        canWrite(d.projectId) &&
        d.status === "Pending confirmation" ? (
          <Button
            size="sm"
            variant="outline"
            className="h-7 px-2 text-xs"
            onClick={() => {
              setTarget(d);
              setPerson("");
              setDate(d.deliveryDate);
              setMethod(d.deliveryMethod);
            }}
          >
            <CheckCircle2 className="size-3.5" /> Confirm
          </Button>
        ) : null,
    },
  ];

  return (
    <>
      <PageHeader
        title="Customer deliveries"
        subtitle="Select one launch, enter delivered FGPN quantities, upload the signed CMR, then validate after preview."
        crumbs={[{ label: "Delivery" }, { label: "Customer deliveries" }]}
        meta={
          <>
            <StatusBadge tone="warn">{pending.length} awaiting confirmation</StatusBadge>
            <StatusBadge tone="neutral">{planned.length} planned</StatusBadge>
            <StatusBadge tone="info">Total in scope {money(totalValue)}</StatusBadge>
          </>
        }
      />
      <div className="space-y-4 p-4">
        <Section
          title="Launch delivery method"
          description="One launch can be delivered partially: enter only the FGPN quantities included in this shipment."
          actions={
            <Select
              value={selectedLaunch?.id ?? ""}
              onValueChange={(value) => {
                setSelectedLaunchId(value);
                setDeliveryQty({});
                setCmrFile(null);
              }}
            >
              <SelectTrigger className="h-8 w-72 text-xs">
                <SelectValue placeholder="Select a launch" />
              </SelectTrigger>
              <SelectContent>
                {scopedLaunches.map((launch) => (
                  <SelectItem key={launch.id} value={launch.id}>
                    {launch.ref} - {launch.projectLabel}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          }
        >
          {selectedLaunch ? (
            <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_340px]">
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge tone="info">{selectedLaunch.projectLabel}</StatusBadge>
                  <StatusBadge tone="neutral">
                    Planned {fmtDate(selectedLaunch.plannedDate)}
                  </StatusBadge>
                  <AutoBadge value={selectedLaunch.status} />
                </div>
                <div className="max-h-[320px] overflow-auto rounded-md border border-border">
                  <table className="w-full min-w-[720px] text-sm">
                    <thead className="sticky top-0 z-10">
                      <tr className="border-b border-border bg-muted/90">
                        <th className="label-caps px-3 py-2 text-left">FGPN</th>
                        <th className="label-caps px-3 py-2 text-left">Description</th>
                        <th className="label-caps px-3 py-2 text-right">Planned</th>
                        <th className="label-caps px-3 py-2 text-right">Already delivered</th>
                        <th className="label-caps px-3 py-2 text-right">Remaining</th>
                        <th className="label-caps px-3 py-2 text-right">Delivered now</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedLaunch.lines.map((line) => (
                        <tr key={line.id} className="border-b border-border last:border-0">
                          <td className="num px-3 py-2 font-medium">{line.fgpn}</td>
                          <td className="px-3 py-2 text-xs">{line.description}</td>
                          <td className="num px-3 py-2 text-right">{nf.format(line.plannedQty)}</td>
                          <td className="num px-3 py-2 text-right">
                            {nf.format(line.deliveredQty)}
                          </td>
                          <td className="num px-3 py-2 text-right">
                            {nf.format(line.remainingQty)}
                          </td>
                          <td className="px-3 py-2">
                            <Input
                              type="number"
                              min={0}
                              max={line.remainingQty}
                              value={deliveryQty[line.id] ?? ""}
                              onChange={(event) =>
                                setDeliveryQty((current) => ({
                                  ...current,
                                  [line.id]: event.target.value,
                                }))
                              }
                              className="num h-8 text-right text-xs"
                              disabled={!selectedCanWrite}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="space-y-3">
                <FileDropzone
                  accept={[".pdf"]}
                  label="Upload signed CMR"
                  hint="PDF proof required before validation."
                  rejectMessage="The signed CMR must be a PDF."
                  onFileAccepted={setCmrFile}
                  disabled={!selectedCanWrite}
                />
                <dl className="rounded-md border border-border bg-muted/30 p-3 text-xs">
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">FGPN lines</dt>
                    <dd className="num">{selectedDeliveryLines.length}</dd>
                  </div>
                  <div className="mt-1 flex justify-between gap-3">
                    <dt className="text-muted-foreground">Quantity now</dt>
                    <dd className="num">{nf.format(selectedTotalQty)}</dd>
                  </div>
                  <div className="mt-1 flex justify-between gap-3">
                    <dt className="text-muted-foreground">CMR</dt>
                    <dd className="num text-right">{cmrFile?.name ?? "Not uploaded"}</dd>
                  </div>
                </dl>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8"
                    disabled={!cmrPreviewUrl}
                    onClick={() => setCmrPreviewOpen(true)}
                  >
                    <Eye className="size-3.5" /> Preview CMR
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    className="h-8"
                    disabled={
                      !selectedCanWrite ||
                      !cmrFile ||
                      selectedDeliveryLines.length === 0 ||
                      selectedDeliveryLines.some((line) => line.entered > line.remainingQty)
                    }
                    onClick={() => setConfirmLaunchOpen(true)}
                  >
                    <Truck className="size-3.5" /> Validate delivery
                  </Button>
                </div>
                {!selectedCanWrite && (
                  <p className="rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                    Launch Managers can inspect other engineers' deliveries, but cannot change them.
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="p-4 text-sm text-muted-foreground">
              No launch is available in your project scope.
            </div>
          )}
        </Section>

        <Section
          title="Delivery register"
          actions={
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger className="h-8 w-52 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="Planned">Planned</SelectItem>
                <SelectItem value="Pending confirmation">Pending confirmation</SelectItem>
                <SelectItem value="Delivered">Delivered</SelectItem>
              </SelectContent>
            </Select>
          }
        >
          <DataTable
            rows={rows}
            columns={columns}
            rowKey={(d) => d.id}
            searchable={(d) => `${d.ref} ${d.fgpn} ${d.description} ${d.deliveryMethod}`}
            searchPlaceholder="Search reference, part number or method…"
            rowTone={(d) => (d.status === "Pending confirmation" ? "warn" : undefined)}
            emptyTitle="No delivery in scope"
          />
        </Section>
      </div>

      <ConfirmDialog
        open={target !== null}
        onOpenChange={(v) => !v && setTarget(null)}
        title={`Confirm delivery ${target?.ref ?? ""}`}
        description="Recording a confirmation sets the delivery to Delivered and updates the delivered quantity on the purchase order."
        confirmLabel="Record confirmation"
        disabled={!person || !date}
        onConfirm={() => {
          toast.success(`Delivery ${target?.ref} confirmed by ${person}.`);
          setTarget(null);
        }}
      >
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label className="text-xs">Confirmed by (customer contact)</Label>
            <Input
              value={person}
              onChange={(e) => setPerson(e.target.value)}
              placeholder="Name of the person who confirmed"
              className="h-8 text-xs"
            />
          </div>
          <div className="grid gap-1.5">
            <Label className="text-xs">Confirmation method</Label>
            <Select value={method} onValueChange={setMethod}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {["Signed CMR returned", "E-mail confirmation", "Customer portal receipt"].map(
                  (m) => (
                    <SelectItem key={m} value={m}>
                      {m}
                    </SelectItem>
                  ),
                )}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label className="text-xs">Confirmation date</Label>
            <Input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="h-8 text-xs"
            />
          </div>
        </div>
      </ConfirmDialog>

      <Dialog open={cmrPreviewOpen} onOpenChange={setCmrPreviewOpen}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>CMR verification</DialogTitle>
          </DialogHeader>
          {cmrPreviewUrl && (
            <iframe
              title="Signed CMR preview"
              src={cmrPreviewUrl}
              className="h-[70vh] w-full rounded-md border border-border"
            />
          )}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={confirmLaunchOpen}
        onOpenChange={setConfirmLaunchOpen}
        title={`Validate delivery for ${selectedLaunch?.ref ?? ""}`}
        description="The entered FGPN quantities will be recorded against this launch, and the signed CMR PDF will be stored as proof."
        confirmLabel="Validate delivery"
        disabled={submittingLaunch || !cmrFile || selectedDeliveryLines.length === 0}
        onConfirm={() => {
          void submitLaunchDelivery(
            selectedLaunch,
            selectedDeliveryLines,
            cmrFile,
            user.username,
            setSubmittingLaunch,
            setConfirmLaunchOpen,
          );
        }}
      >
        <div className="rounded-md border border-border bg-muted/30 p-3 text-xs">
          <p className="font-medium text-foreground">{cmrFile?.name}</p>
          <p className="mt-1 text-muted-foreground">
            {selectedDeliveryLines.length} FGPN line(s), {nf.format(selectedTotalQty)} total unit(s)
          </p>
        </div>
      </ConfirmDialog>
    </>
  );
}

async function submitLaunchDelivery(
  launch: LaunchDeliveryOption | undefined,
  lines: Array<LaunchDeliveryLine & { entered: number }>,
  cmrFile: File | null,
  username: string,
  setSubmitting: (value: boolean) => void,
  setOpen: (value: boolean) => void,
) {
  if (!launch || !cmrFile) return;
  setSubmitting(true);
  try {
    if (launch.apiId) {
      const body = new FormData();
      body.append(
        "payload",
        JSON.stringify({
          lines: lines.map((line) => ({
            launch_fgpn_id: line.apiId,
            delivered_quantity: line.entered,
          })),
        }),
      );
      body.append("cmr_file", cmrFile);
      body.append("uploaded_by", username);
      const response = await apiFetch(`/customer-deliveries/launches/${launch.apiId}/confirm`, {
        method: "POST",
        body,
      });
      if (!response.ok) await throwApiError(response);
      const result = await response.json();
      toast.success(`CMR ${result.file_name} stored for ${launch.ref}.`);
    } else {
      toast.success(`CMR ${cmrFile.name} validated for ${launch.ref}.`);
    }
    setOpen(false);
  } catch (error) {
    toast.error(readApiError(error, "Could not validate the customer delivery."));
  } finally {
    setSubmitting(false);
  }
}

function deriveDemoLaunches(): LaunchDeliveryOption[] {
  return simulations
    .filter((simulation) => simulation.approved)
    .map((simulation, index) => {
      const poLines = simulation.poIds.flatMap((poId) => findPo(poId)?.lines ?? []);
      return {
        id: simulation.id,
        ref: `Launch ${simulation.ref}`,
        projectId: simulation.projectId,
        projectLabel: projectLabel(simulation.projectId),
        status: "IN_PROGRESS",
        plannedDate: simulation.approvedAt?.slice(0, 10) ?? simulation.runAt.slice(0, 10),
        lines: poLines.map((line) => ({
          id: `${simulation.id}-${line.id}`,
          fgpn: line.fgpn,
          description: line.description ?? "",
          plannedQty: line.quantity,
          deliveredQty: line.deliveredQuantity,
          remainingQty: Math.max(line.quantity - line.deliveredQuantity, 0),
        })),
      };
    })
    .filter((launch) => launch.lines.length > 0)
    .map((launch, index) => ({ ...launch, ref: `Launch #${index + 1} - ${launch.ref}` }));
}

function mapApiLaunchDelivery(raw: ApiLaunchDelivery): LaunchDeliveryOption {
  const projectId =
    resolveProjectId(raw.project_code) ?? raw.project_code ?? String(raw.project_id ?? "");
  return {
    id: `API-LAUNCH-${raw.launch_id}`,
    apiId: raw.launch_id,
    ref: `Launch #${raw.launch_id}`,
    projectId,
    projectLabel: raw.project_code
      ? `${raw.project_code}${raw.project_name ? ` - ${raw.project_name}` : ""}`
      : String(raw.project_id ?? ""),
    status: raw.status,
    plannedDate: raw.planned_date,
    lines: raw.lines.map((line) => ({
      id: `API-LFGPN-${line.launch_fgpn_id}`,
      apiId: line.launch_fgpn_id,
      fgpn: line.fgpn_code,
      description: line.description ?? "",
      plannedQty: Number(line.planned_quantity),
      deliveredQty: Number(line.delivered_quantity),
      remainingQty: Number(line.remaining_quantity),
    })),
  };
}

interface LaunchDeliveryLine {
  id: string;
  apiId?: number;
  fgpn: string;
  description: string;
  plannedQty: number;
  deliveredQty: number;
  remainingQty: number;
}

interface LaunchDeliveryOption {
  id: string;
  apiId?: number;
  ref: string;
  projectId: string;
  projectLabel: string;
  status: string;
  plannedDate: string;
  lines: LaunchDeliveryLine[];
}

interface ApiLaunchDelivery {
  launch_id: number;
  project_id: number | null;
  project_code: string | null;
  project_name: string | null;
  status: string;
  planned_date: string;
  lines: Array<{
    launch_fgpn_id: number;
    fgpn_code: string;
    description: string | null;
    planned_quantity: string | number;
    delivered_quantity: string | number;
    remaining_quantity: string | number;
  }>;
}
