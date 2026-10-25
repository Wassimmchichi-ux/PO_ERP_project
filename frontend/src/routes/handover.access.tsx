import { createFileRoute } from "@tanstack/react-router";
import { useRef, useState } from "react";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import { toast } from "sonner";
import { FileCheck2, FileText, KeyRound, Printer } from "lucide-react";
import { PageHeader, Section } from "@/components/erp/PageHeader";
import { StatusBadge } from "@/components/erp/StatusBadge";
import { AccessDenied, EmptyState } from "@/components/erp/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSession } from "@/lib/erp/session";
import { deliveryInstructions, projectLabel, resolveProjectId } from "@/lib/erp/data";
import { codeValidity, fmtDateTime, nf } from "@/lib/erp/format";
import type { DeliveryInstruction } from "@/lib/erp/types";
import { footerSignature, pageTitle } from "@/lib/erp/appInfo";
import { apiFetch, readApiError, throwApiError } from "@/lib/erp/api";

export const Route = createFileRoute("/handover/access")({
  head: () => ({
    meta: [
      { title: pageTitle("Delivery Code Access") },
      {
        name: "description",
        content:
          "Warehouse terminal screen: enter the delivery access code to reveal the material list to prepare and record the receiver.",
      },
      { property: "og:title", content: pageTitle("Delivery Code Access") },
      {
        property: "og:description",
        content: "Single-use, time-limited codes open the corresponding delivery instruction.",
      },
    ],
  }),
  component: CodeAccessPage,
});

function CodeAccessPage() {
  const { can } = useSession();
  const [code, setCode] = useState("");
  const [opened, setOpened] = useState<DeliveryInstruction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [receiver, setReceiver] = useState("");
  const [leader, setLeader] = useState("");
  const [backendEnabled, setBackendEnabled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const signedInputRef = useRef<HTMLInputElement>(null);

  if (!can("handover.code.access")) return <AccessDenied what="the delivery code terminal" />;

  async function submit() {
    const normalized = code.trim();
    setLoading(true);
    setError(null);

    try {
      const apiInstruction = await fetchHandoverByCode(normalized);
      setOpened(apiInstruction);
      setReceiver(apiInstruction.receiverName ?? "");
      setLeader(apiInstruction.warehouseTeamLeader ?? "");
      setBackendEnabled(true);
      return;
    } catch (apiError) {
      const match = deliveryInstructions.find((d) => d.code === normalized);
      if (!match) {
        setOpened(null);
        setBackendEnabled(false);
        setError(
          readApiError(
            apiError,
            "No delivery instruction matches this code. Check the code with the launch team.",
          ),
        );
        return;
      }

      setBackendEnabled(false);
      const v = codeValidity(match.codeExpiresAt, match.codeUsed);
      if (v.state === "expired") {
        setOpened(null);
        setError(`Code expired on ${fmtDateTime(match.codeExpiresAt)}. Request a new code.`);
        return;
      }

      setOpened(match);
      setReceiver(match.receiverName ?? "");
      setLeader(match.warehouseTeamLeader ?? "");
    } finally {
      setLoading(false);
    }
  }

  async function confirmCollection() {
    if (!opened || !receiver || !leader) return;
    if (!backendEnabled) {
      toast.success(
        `Code marked as used for ${opened.ref}; delivery document generated for signature.`,
      );
      setOpened(null);
      setCode("");
      setReceiver("");
      setLeader("");
      return;
    }

    setLoading(true);
    try {
      const updated = await confirmHandoverCollection(code.trim(), receiver, leader);
      setOpened(updated);
      toast.success(`Collection recorded for ${updated.ref}. The signed PDF can now be uploaded.`);
    } catch (err) {
      toast.error(readApiError(err, "Could not confirm the handover collection."));
    } finally {
      setLoading(false);
    }
  }

  function openSignDocument() {
    if (!opened) return;
    const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.text("Warehouse handover sign-off", 14, 18);
    doc.setFontSize(10);
    doc.text(opened.ref, 196, 18, { align: "right" });

    autoTable(doc, {
      startY: 28,
      head: [["Field", "Value"]],
      body: [
        ["Project", projectLabel(opened.projectId)],
        ["Receiver", receiver || opened.receiverName || "-"],
        ["Warehouse team leader", leader || opened.warehouseTeamLeader || "-"],
        ["Required at cutting area", fmtDateTime(opened.requiredAt)],
      ],
      theme: "grid",
      styles: { cellPadding: 2, fontSize: 9 },
    });

    autoTable(doc, {
      startY: 68,
      head: [["Material", "Description", "Roll size", "Quantity"]],
      body: opened.items.map((item) => [
        item.materialPartNumber,
        item.description,
        item.rollSize ? `${nf.format(item.rollSize)} m` : "-",
        `${nf.format(item.quantity)} ${item.unit}`,
      ]),
      theme: "striped",
      styles: { cellPadding: 2, fontSize: 9 },
      columnStyles: {
        2: { halign: "right" },
        3: { halign: "right" },
      },
    });

    const signatureY = 190;
    doc.roundedRect(14, signatureY, 84, 34, 2, 2);
    doc.roundedRect(112, signatureY, 84, 34, 2, 2);
    doc.setFontSize(8);
    doc.text("RECEIVER SIGNATURE", 18, signatureY + 8);
    doc.text("WAREHOUSE TEAM LEADER", 116, signatureY + 8);
    doc.setFontSize(7);
    doc.setTextColor(100, 116, 139);
    doc.text(footerSignature, 105, 282, { align: "center" });
    window.open(URL.createObjectURL(doc.output("blob")), "_blank", "noopener,noreferrer");
  }

  async function uploadSignedDocument(file: File | undefined) {
    if (!file || !opened) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Upload the signed handover proof as a PDF.");
      return;
    }
    if (!backendEnabled) {
      toast.success(`${file.name} selected for the demo handover.`);
      return;
    }

    setUploading(true);
    try {
      const updated = await uploadSignedHandoverDocument(code.trim(), file, leader);
      setOpened(updated);
      toast.success(`${file.name} uploaded and attached to ${updated.ref}.`);
    } catch (err) {
      toast.error(readApiError(err, "Could not upload the signed PDF."));
    } finally {
      setUploading(false);
    }
  }

  function resetTerminal() {
    setOpened(null);
    setCode("");
    setReceiver("");
    setLeader("");
    setError(null);
  }

  return (
    <>
      <PageHeader
        title="Delivery code access"
        subtitle="Warehouse team leaders open one instruction, prepare the stock units, print the sign-off, then upload the signed PDF proof."
        crumbs={[{ label: "Delivery", to: "/handover" }, { label: "Code access" }]}
      />

      <div className="grid gap-4 p-4 xl:grid-cols-[380px_minmax(0,1fr)]">
        <Section title="Enter delivery code">
          <div className="space-y-3 p-4">
            <div className="grid gap-1.5">
              <Label className="text-xs">6-digit access code</Label>
              <Input
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                inputMode="numeric"
                placeholder="000000"
                className="num h-12 text-center text-2xl tracking-[0.5em]"
              />
            </div>
            <Button className="h-9 w-full" disabled={code.length !== 6 || loading} onClick={submit}>
              <KeyRound className="size-4" /> Open delivery instruction
            </Button>
            {error && (
              <p className="rounded-md border border-danger/30 bg-danger-soft px-3 py-2 text-xs text-danger">
                {error}
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              The code identifies the instruction; the signed PDF remains the proof used by the
              launch engineer to validate the handover.
            </p>
          </div>
        </Section>

        <Section title="Material to prepare">
          {!opened ? (
            <EmptyState
              title="No instruction opened"
              description="Enter a valid delivery code to display the materials the warehouse has to prepare."
            />
          ) : (
            <div className="space-y-4 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="num text-sm font-semibold">{opened.ref}</span>
                <StatusBadge tone="info">{projectLabel(opened.projectId)}</StatusBadge>
                <StatusBadge tone="warn">Required {fmtDateTime(opened.requiredAt)}</StatusBadge>
                <StatusBadge tone="ok">
                  {codeValidity(opened.codeExpiresAt, opened.codeUsed).label}
                </StatusBadge>
                {backendEnabled && <StatusBadge tone="ok">Backend connected</StatusBadge>}
              </div>

              <div className="max-h-[320px] overflow-auto rounded-md border border-border">
                <table className="w-full min-w-[680px] text-sm">
                  <thead className="sticky top-0 z-10">
                    <tr className="border-b border-border bg-muted/90">
                      <th className="label-caps px-3 py-2 text-left">Material</th>
                      <th className="label-caps px-3 py-2 text-left">Description</th>
                      <th className="label-caps px-3 py-2 text-right">Roll size</th>
                      <th className="label-caps px-3 py-2 text-right">Quantity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {opened.items.map((i) => (
                      <tr
                        key={i.materialPartNumber}
                        className="border-b border-border last:border-0"
                      >
                        <td className="num px-3 py-2 font-medium">{i.materialPartNumber}</td>
                        <td className="px-3 py-2 text-xs">{i.description}</td>
                        <td className="num px-3 py-2 text-right">
                          {i.rollSize ? `${nf.format(i.rollSize)} m` : "—"}
                        </td>
                        <td className="num px-3 py-2 text-right">
                          {nf.format(i.quantity)} {i.unit}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="grid gap-3 lg:grid-cols-2">
                <div className="grid gap-1.5">
                  <Label className="text-xs">Receiver name</Label>
                  <Input
                    value={receiver}
                    onChange={(e) => setReceiver(e.target.value)}
                    placeholder="Person collecting the material"
                    className="h-8 text-xs"
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label className="text-xs">Warehouse team leader</Label>
                  <Input
                    value={leader}
                    onChange={(e) => setLeader(e.target.value)}
                    placeholder="Team leader handing over stock units"
                    className="h-8 text-xs"
                  />
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  className="h-8"
                  disabled={!receiver || !leader || loading}
                  onClick={confirmCollection}
                >
                  <FileText className="size-3.5" /> Confirm collection
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="h-8"
                  disabled={!receiver || !leader}
                  onClick={openSignDocument}
                >
                  <Printer className="size-3.5" /> Open sign-off PDF
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="h-8"
                  disabled={!receiver || !leader || uploading}
                  onClick={() => signedInputRef.current?.click()}
                >
                  <FileCheck2 className="size-3.5" /> Upload signed PDF
                </Button>
                <Button type="button" variant="ghost" className="h-8" onClick={resetTerminal}>
                  Clear
                </Button>
                <input
                  ref={signedInputRef}
                  type="file"
                  accept="application/pdf,.pdf"
                  className="hidden"
                  onChange={(event) => uploadSignedDocument(event.target.files?.[0])}
                />
              </div>

              {opened.signedDocId && (
                <p className="rounded-md border border-ok/30 bg-ok-soft px-3 py-2 text-xs text-ok">
                  Signed document {opened.signedDocId} is attached and ready for launch engineer
                  validation.
                </p>
              )}
            </div>
          )}
        </Section>
      </div>
    </>
  );
}

async function fetchHandoverByCode(code: string): Promise<DeliveryInstruction> {
  const response = await apiFetch(`/handovers/access/${encodeURIComponent(code)}`);
  if (!response.ok) await throwApiError(response);
  return mapApiHandover(await response.json());
}

async function confirmHandoverCollection(
  code: string,
  receiverName: string,
  warehouseTeamLeaderName: string,
): Promise<DeliveryInstruction> {
  const response = await apiFetch(`/handovers/access/${encodeURIComponent(code)}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      receiver_name: receiverName,
      warehouse_team_leader_name: warehouseTeamLeaderName,
    }),
  });
  if (!response.ok) await throwApiError(response);
  return mapApiHandover(await response.json());
}

async function uploadSignedHandoverDocument(
  code: string,
  file: File,
  uploadedBy: string,
): Promise<DeliveryInstruction> {
  const body = new FormData();
  body.append("file", file);
  body.append("uploaded_by", uploadedBy);
  const response = await apiFetch(`/handovers/access/${encodeURIComponent(code)}/signed-document`, {
    method: "POST",
    body,
  });
  if (!response.ok) await throwApiError(response);
  const result = await response.json();
  return mapApiHandover(result.handover);
}

function mapApiHandover(raw: ApiHandoverAccessResponse): DeliveryInstruction {
  const projectId =
    resolveProjectId(raw.project_code) ?? raw.project_code ?? String(raw.project_id ?? "");
  return {
    id: `API-DI-${raw.delivery_inst_id}`,
    ref: raw.ref,
    projectId,
    simulationId: `SIM-${raw.simulation_id}`,
    createdAt: raw.created_at,
    createdBy: raw.created_by ?? "system",
    requiredAt: raw.required_at,
    code: raw.delivery_code,
    codeExpiresAt: raw.code_expires_at,
    codeUsed: raw.code_used,
    status: mapApiStatus(raw.status),
    ...(raw.receiver_name == null ? {} : { receiverName: raw.receiver_name }),
    ...(raw.warehouse_team_leader_name == null
      ? {}
      : { warehouseTeamLeader: raw.warehouse_team_leader_name }),
    ...(raw.signed_document_id ? { signedDocId: `DOC-${raw.signed_document_id}` } : {}),
    items: raw.items.map((item) => ({
      materialPartNumber: item.material_part_number,
      description: item.description,
      ...(item.roll_size === null ? {} : { rollSize: Number(item.roll_size) }),
      quantity: Number(item.quantity),
      unit: item.unit === "pcs" ? "pcs" : "m",
    })),
  };
}

function mapApiStatus(status: string): DeliveryInstruction["status"] {
  switch (status) {
    case "Document_Generated":
      return "Document generated";
    case "Signed_Uploaded":
      return "Awaiting validation";
    case "Validated":
      return "Validated";
    case "Expired":
      return "Code expired";
    default:
      return "Code issued";
  }
}

interface ApiHandoverAccessResponse {
  delivery_inst_id: number;
  ref: string;
  simulation_id: number;
  project_id: number | null;
  project_code: string | null;
  project_name: string | null;
  created_at: string;
  created_by: string | null;
  required_at: string;
  delivery_code: string;
  code_expires_at: string;
  code_used: boolean;
  status: string;
  receiver_name: string | null;
  warehouse_team_leader_name: string | null;
  signed_document_id: number | null;
  items: Array<{
    material_part_number: string;
    description: string;
    roll_size: string | number | null;
    quantity: string | number;
    unit: string;
  }>;
}
