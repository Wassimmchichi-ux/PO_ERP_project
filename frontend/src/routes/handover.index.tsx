import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import { toast } from "sonner";
import { Eye, FileDown, FileText, KeyRound, ShieldCheck } from "lucide-react";
import { PageHeader, Section, KeyValue } from "@/components/erp/PageHeader";
import { AutoBadge, StatusBadge } from "@/components/erp/StatusBadge";
import { AccessDenied, EmptyState } from "@/components/erp/EmptyState";
import { ConfirmDialog } from "@/components/erp/ConfirmDialog";
import { FileDropzone } from "@/components/erp/FileDropzone";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useProjectScope, useSession } from "@/lib/erp/session";
import { deliveryInstructions, documents, projectLabel, simulations } from "@/lib/erp/data";
import { codeValidity, fmtDateTime, nf } from "@/lib/erp/format";
import type { DeliveryInstruction, ErpDocument } from "@/lib/erp/types";
import { appInfo, footerSignature, pageTitle } from "@/lib/erp/appInfo";

function createSignedReceptionPdf(instruction: DeliveryInstruction, documentRecord: ErpDocument) {
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const primaryColor: [number, number, number] = [44, 41, 61];
  const accentColor: [number, number, number] = [217, 119, 6];

  doc.setFillColor(...primaryColor);
  doc.rect(0, 0, 210, 24, "F");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(14);
  doc.setTextColor(255, 255, 255);
  doc.text(appInfo.productName.toUpperCase(), 14, 10);
  doc.setFontSize(9);
  doc.setTextColor(226, 232, 240);
  doc.text("SIGNED WAREHOUSE RECEPTION DOCUMENT", 14, 17);
  doc.setFontSize(10);
  doc.setTextColor(255, 255, 255);
  doc.text(instruction.ref, 196, 14, { align: "right" });

  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.setTextColor(30, 41, 59);
  doc.text("Reception approval summary", 14, 36);

  autoTable(doc, {
    startY: 42,
    head: [["Field", "Value", "Field", "Value"]],
    body: [
      ["Document ID", documentRecord.id, "File", documentRecord.fileName],
      [
        "Project",
        projectLabel(instruction.projectId),
        "Source simulation",
        instruction.simulationId,
      ],
      [
        "Receiver",
        instruction.receiverName ?? "Not recorded",
        "Warehouse leader",
        instruction.warehouseTeamLeader ?? "Not recorded",
      ],
      [
        "Uploaded",
        fmtDateTime(documentRecord.uploadedAt),
        "Uploaded by",
        documentRecord.uploadedBy,
      ],
      [
        "Required at cutting area",
        fmtDateTime(instruction.requiredAt),
        "File size",
        `${nf.format(documentRecord.sizeKb)} KB`,
      ],
    ],
    theme: "grid",
    headStyles: { fillColor: primaryColor, textColor: [255, 255, 255], fontSize: 8 },
    bodyStyles: { fontSize: 8, textColor: [51, 65, 85] },
    styles: { cellPadding: 2 },
    margin: { left: 14, right: 14 },
  });

  const summaryY = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY;
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.setTextColor(30, 41, 59);
  doc.text("Materials received", 14, summaryY + 10);

  autoTable(doc, {
    startY: summaryY + 16,
    head: [["Material", "Description", "Roll size", "Quantity"]],
    body: instruction.items.map((item) => [
      item.materialPartNumber,
      item.description,
      item.rollSize ? `${nf.format(item.rollSize)} m` : "-",
      `${nf.format(item.quantity)} ${item.unit}`,
    ]),
    theme: "striped",
    headStyles: { fillColor: accentColor, textColor: [255, 255, 255], fontSize: 8 },
    bodyStyles: { fontSize: 8, textColor: [51, 65, 85] },
    columnStyles: {
      0: { fontStyle: "bold" },
      2: { halign: "right" },
      3: { halign: "right", fontStyle: "bold" },
    },
    styles: { cellPadding: 2 },
    margin: { left: 14, right: 14 },
  });

  const materialY = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY;
  const signatureY = Math.max(materialY + 16, 160);

  doc.setDrawColor(203, 213, 225);
  doc.setLineWidth(0.2);
  doc.roundedRect(14, signatureY, 84, 34, 2, 2);
  doc.roundedRect(112, signatureY, 84, 34, 2, 2);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(8);
  doc.setTextColor(100, 116, 139);
  doc.text("RECEIVER SIGNATURE", 18, signatureY + 8);
  doc.text("WAREHOUSE APPROVAL", 116, signatureY + 8);

  doc.setFont("times", "italic");
  doc.setFontSize(18);
  doc.setTextColor(30, 41, 59);
  doc.text(instruction.receiverName ?? "Signed receiver", 18, signatureY + 23);
  doc.text(instruction.warehouseTeamLeader ?? "Warehouse leader", 116, signatureY + 23);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(8);
  doc.setTextColor(100, 116, 139);
  doc.text(`${footerSignature} | Stored signed scan reviewed for handover validation.`, 105, 282, {
    align: "center",
  });

  return doc.output("blob");
}

export const Route = createFileRoute("/handover/")({
  head: () => ({
    meta: [
      { title: pageTitle("Warehouse Handover") },
      {
        name: "description",
        content:
          "Delivery instructions from approved launches: issue access codes, generate the warehouse delivery document, upload the signed reception and validate the handover.",
      },
      { property: "og:title", content: pageTitle("Warehouse Handover") },
      {
        property: "og:description",
        content: "Controlled material handover from the warehouse to the cutting area.",
      },
    ],
  }),
  component: HandoverPage,
});

function HandoverPage() {
  const { can, canWrite } = useSession();
  const scope = useProjectScope();
  const visible = deliveryInstructions.filter((d) => scope.inScope(d.projectId));
  const [selectedId, setSelectedId] = useState(visible[0]?.id ?? "");
  const [validateOpen, setValidateOpen] = useState(false);
  const [signedDocOpen, setSignedDocOpen] = useState(false);
  const [signedDocPdfUrl, setSignedDocPdfUrl] = useState<string | null>(null);
  const [receiver, setReceiver] = useState("");

  const selected = visible.find((d) => d.id === selectedId) ?? visible[0];
  const writable = selected ? canWrite(selected.projectId) : false;
  const validity = selected ? codeValidity(selected.codeExpiresAt, selected.codeUsed) : null;
  const sim = selected ? simulations.find((s) => s.id === selected.simulationId) : undefined;
  const signedDoc = selected?.signedDocId
    ? documents.find((doc) => doc.id === selected.signedDocId)
    : undefined;

  useEffect(() => {
    if (!signedDocOpen || !selected || !signedDoc) {
      setSignedDocPdfUrl(null);
      return;
    }

    const url = URL.createObjectURL(createSignedReceptionPdf(selected, signedDoc));
    setSignedDocPdfUrl(url);

    return () => URL.revokeObjectURL(url);
  }, [selected, signedDoc, signedDocOpen]);

  if (!can("handover.instruction.create") && !can("handover.validate")) {
    return <AccessDenied what="warehouse handovers" />;
  }

  const awaiting = visible.filter((d) => d.status === "Awaiting validation").length;
  const expired = visible.filter((d) => d.status === "Code expired").length;

  return (
    <>
      <PageHeader
        title="Warehouse handover"
        subtitle="Material leaves ERP warehouse stock only after a validated, signed handover."
        crumbs={[{ label: "Delivery" }, { label: "Warehouse handover" }]}
        meta={
          <>
            <StatusBadge tone="warn">{awaiting} awaiting validation</StatusBadge>
            <StatusBadge tone="danger">{expired} expired codes</StatusBadge>
          </>
        }
        actions={
          <Button asChild variant="outline" size="sm" className="h-8">
            <Link to="/handover/access">
              <KeyRound className="size-3.5" /> Code access screen
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 p-4 xl:grid-cols-[380px_minmax(0,1fr)]">
        <Section title="Delivery instructions" description="Issued from approved launch decisions.">
          {visible.length === 0 ? (
            <EmptyState title="No delivery instruction in scope" />
          ) : (
            <ul className="divide-y divide-border">
              {visible.map((d) => {
                const v = codeValidity(d.codeExpiresAt, d.codeUsed);
                return (
                  <li key={d.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(d.id)}
                      className={`w-full px-4 py-2.5 text-left transition-colors hover:bg-muted/60 ${
                        selected?.id === d.id ? "bg-muted" : ""
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="num text-sm font-medium">{d.ref}</span>
                        <AutoBadge value={d.status} />
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {projectLabel(d.projectId)} · {d.items.length} materials ·{" "}
                        {v.state === "expired" ? (
                          <span className="text-danger">code expired</span>
                        ) : (
                          v.label
                        )}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Section>

        {selected && (
          <div className="space-y-4">
            <Section
              title={`Instruction ${selected.ref}`}
              actions={
                <div className="flex gap-2">
                  {can("handover.document.generate") && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8"
                      disabled={!writable}
                      onClick={() =>
                        toast.success(`Warehouse delivery document generated for ${selected.ref}.`)
                      }
                    >
                      <FileDown className="size-3.5" /> Generate delivery document
                    </Button>
                  )}
                  {can("handover.validate") && (
                    <Button
                      size="sm"
                      className="h-8"
                      disabled={
                        !writable || selected.status === "Validated" || !selected.signedDocId
                      }
                      onClick={() => setValidateOpen(true)}
                    >
                      <ShieldCheck className="size-3.5" /> Validate handover
                    </Button>
                  )}
                </div>
              }
            >
              <KeyValue
                columns={4}
                items={[
                  { label: "Project", value: projectLabel(selected.projectId) },
                  { label: "Source simulation", value: sim?.ref ?? selected.simulationId },
                  {
                    label: "Created",
                    value: `${fmtDateTime(selected.createdAt)} · ${selected.createdBy}`,
                  },
                  { label: "Required in cutting area", value: fmtDateTime(selected.requiredAt) },
                  {
                    label: "Access code",
                    value: (
                      <span className="num tracking-widest">
                        {selected.codeUsed ? "•••••• (used)" : selected.code}
                      </span>
                    ),
                  },
                  {
                    label: "Code validity",
                    value: (
                      <StatusBadge
                        tone={
                          validity?.state === "valid"
                            ? "ok"
                            : validity?.state === "used"
                              ? "info"
                              : "danger"
                        }
                      >
                        {validity?.label}
                      </StatusBadge>
                    ),
                  },
                  { label: "Receiver", value: selected.receiverName ?? "Not collected yet" },
                  {
                    label: "Warehouse team leader",
                    value: selected.warehouseTeamLeader ?? "—",
                  },
                ]}
              />
            </Section>

            <Section title="Materials to hand over">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/60">
                    <th className="label-caps px-4 py-2 text-left">Material</th>
                    <th className="label-caps px-4 py-2 text-left">Description</th>
                    <th className="label-caps px-4 py-2 text-right">Roll size</th>
                    <th className="label-caps px-4 py-2 text-right">Quantity</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.items.map((i) => (
                    <tr key={i.materialPartNumber} className="border-b border-border last:border-0">
                      <td className="num px-4 py-1.5 font-medium">{i.materialPartNumber}</td>
                      <td className="px-4 py-1.5 text-xs">{i.description}</td>
                      <td className="num px-4 py-1.5 text-right">
                        {i.rollSize ? `${nf.format(i.rollSize)} m` : "—"}
                      </td>
                      <td className="num px-4 py-1.5 text-right">
                        {nf.format(i.quantity)} {i.unit}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>

            <Section
              title="Signed reception document"
              description="The physical document signed by the receiver must be stored before validation."
            >
              <div className="space-y-3 p-4">
                {selected.signedDocId ? (
                  <button
                    type="button"
                    onClick={() => setSignedDocOpen(true)}
                    className="flex w-full items-center justify-between rounded-md border border-border bg-muted/40 px-3 py-2 text-left text-sm transition-colors hover:border-info/40 hover:bg-info/10 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <FileText className="size-4 shrink-0 text-info" />
                      <span className="truncate num">
                        {selected.signedDocId} — signed reception scan
                      </span>
                    </span>
                    <span className="flex shrink-0 items-center gap-2">
                      <Eye className="size-4 text-muted-foreground" />
                      <StatusBadge tone="ok">Stored</StatusBadge>
                    </span>
                  </button>
                ) : (
                  <StatusBadge tone="warn">No signed document stored yet</StatusBadge>
                )}
                {can("handover.signed.upload") && (
                  <FileDropzone
                    accept={[".pdf"]}
                    label="Drop the signed reception document"
                    hint="Scanned PDF signed by the receiver and the warehouse team leader"
                    rejectMessage="Signed reception documents must be PDF."
                    disabled={!writable}
                    onAccepted={(n) => toast.success(`${n} linked to ${selected.ref}.`)}
                  />
                )}
              </div>
            </Section>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={validateOpen}
        onOpenChange={setValidateOpen}
        title={`Validate handover ${selected?.ref ?? ""}`}
        description="Validation deducts the handed-over quantities from warehouse practical stock and records the movement in the stock history. This cannot be undone."
        confirmLabel="Validate and deduct stock"
        disabled={!receiver}
        onConfirm={() => {
          toast.success(`Handover ${selected?.ref} validated; warehouse stock updated.`);
          setValidateOpen(false);
        }}
      >
        <div className="grid gap-1.5">
          <Label className="text-xs">Receiver name (as signed)</Label>
          <Input
            value={receiver}
            onChange={(e) => setReceiver(e.target.value)}
            placeholder="Person who collected the material"
            className="h-8 text-xs"
          />
        </div>
      </ConfirmDialog>

      <Dialog open={signedDocOpen} onOpenChange={setSignedDocOpen}>
        <DialogContent className="max-w-6xl p-0">
          <DialogHeader className="border-b border-border px-5 py-4">
            <DialogTitle>Signed reception document</DialogTitle>
            <DialogDescription>
              Review the uploaded approval scan before validating the handover.
            </DialogDescription>
          </DialogHeader>

          {selected && signedDoc && (
            <div className="grid max-h-[78vh] gap-4 overflow-y-auto p-5 lg:grid-cols-[260px_minmax(0,1fr)]">
              <div className="space-y-3">
                <div className="rounded-md border border-border bg-muted/30 p-3">
                  <p className="label-caps">Document</p>
                  <p className="mt-1 num text-sm font-semibold text-foreground">{signedDoc.id}</p>
                  <p className="mt-1 break-all text-xs text-muted-foreground">
                    {signedDoc.fileName}
                  </p>
                </div>
                <div className="rounded-md border border-border bg-muted/30 p-3 text-xs">
                  <div className="grid gap-2">
                    <div>
                      <p className="label-caps">Uploaded</p>
                      <p className="mt-1">{fmtDateTime(signedDoc.uploadedAt)}</p>
                    </div>
                    <div>
                      <p className="label-caps">Uploaded by</p>
                      <p className="mt-1 num">{signedDoc.uploadedBy}</p>
                    </div>
                    <div>
                      <p className="label-caps">File size</p>
                      <p className="mt-1 num">{nf.format(signedDoc.sizeKb)} KB</p>
                    </div>
                    <div>
                      <p className="label-caps">Linked handover</p>
                      <p className="mt-1 num">{signedDoc.linkedEntity.ref}</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="min-h-[640px] overflow-hidden rounded-md border border-border bg-muted/30">
                {signedDocPdfUrl ? (
                  <iframe
                    title={`${signedDoc.id} PDF preview`}
                    src={signedDocPdfUrl}
                    className="h-[640px] w-full bg-background"
                  />
                ) : (
                  <div className="flex h-[640px] items-center justify-center text-sm text-muted-foreground">
                    Loading PDF preview...
                  </div>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
