import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  RotateCcw,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader, Section } from "@/components/erp/PageHeader";
import { StatusBadge } from "@/components/erp/StatusBadge";
import { FileDropzone } from "@/components/erp/FileDropzone";
import { ConfirmDialog } from "@/components/erp/ConfirmDialog";
import { AccessDenied } from "@/components/erp/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSession } from "@/lib/erp/session";
import { pageTitle } from "@/lib/erp/appInfo";
import { apiFetch, readApiError, throwApiError } from "@/lib/erp/api";
import { useQueryClient } from "@tanstack/react-query";
import { purchaseOrdersQueryKey } from "@/lib/erp/purchaseOrderApi";

export const Route = createFileRoute("/po-intake")({
  head: () => ({
    meta: [
      { title: pageTitle("Purchase Order Intake") },
      {
        name: "description",
        content:
          "Upload a purchase-order PDF, review every extracted line, validate corrections and import the approved version.",
      },
    ],
  }),
  component: Intake,
});

const LINES_PER_PAGE = 10;
const HEADER_FIELDS = [
  { key: "po_number", label: "PO number", required: true },
  { key: "version", label: "Version", required: true },
  { key: "order_date", label: "Order date" },
  { key: "document_date", label: "Document date" },
  { key: "change_date", label: "Change date" },
  { key: "delivery_date", label: "Latest delivery date" },
  { key: "supplier_number", label: "Supplier number" },
  { key: "replaced_po_number", label: "Replaced PO" },
  { key: "currency", label: "Currency" },
  { key: "stated_total", label: "Stated total" },
] as const;
const LINE_FIELDS = [
  { key: "line_no", label: "Line", required: true, width: "w-20" },
  { key: "part_number", label: "FGPN", required: true, width: "min-w-44" },
  { key: "description", label: "Description", width: "min-w-64" },
  { key: "quantity", label: "Quantity", required: true, width: "w-28" },
  { key: "uom", label: "UOM", width: "w-20" },
  { key: "unit_price", label: "Unit price", required: true, width: "w-32" },
  { key: "total", label: "Line total", required: true, width: "w-32" },
  { key: "due_date", label: "Due date", required: true, width: "w-36" },
] as const;

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
type PoLine = Record<string, JsonValue>;
type PoPayload = Record<string, JsonValue> & { lines?: PoLine[] };

interface ParsedPoResponse {
  parsed_po_id: number;
  source_file_name: string | null;
  has_source_file: boolean;
  parser_name: string | null;
  status: string;
  parsed_payload: PoPayload;
  effective_payload: PoPayload;
  created_at: string;
}
interface ValidationResult {
  parsed_po_id: number;
  status: string;
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  effective_payload: PoPayload;
}
interface ImportResult {
  parsed_po_id: number;
  po_id: number;
  po_version_id: number;
  created_po: boolean;
  line_count: number;
  created_fgpn_ids: number[];
  updated_fgpn_price_history_ids: number[];
}
interface ProjectOption {
  project_id: number;
  project_code: string;
  name: string;
  status: string;
}
interface ReferenceOption {
  id: string;
  list: string;
  value: string;
  detail: string | null;
  active: boolean;
}
interface ImportContext {
  projects: ProjectOption[];
  references: ReferenceOption[];
}

export function Intake() {
  const { can } = useSession();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<ParsedPoResponse | null>(null);
  const [payload, setPayload] = useState<PoPayload | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [sourceName, setSourceName] = useState<string | null>(null);
  const [parsing, setParsing] = useState(false);
  const [validating, setValidating] = useState(false);
  const [importing, setImporting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [uploadKey, setUploadKey] = useState(0);
  const [linePage, setLinePage] = useState(1);
  const [context, setContext] = useState<ImportContext>({ projects: [], references: [] });
  const [contextError, setContextError] = useState<string | null>(null);
  const [projectId, setProjectId] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [contactId, setContactId] = useState("");
  const [deliveryMethodId, setDeliveryMethodId] = useState("");
  const [changeReason, setChangeReason] = useState("");

  useEffect(() => {
    void loadImportContext()
      .then((loaded) => {
        setContext(loaded);
        setProjectId(String(loaded.projects[0]?.project_id ?? ""));
        const customers = activeReferences(loaded.references, "JIT Customers");
        const firstCustomer = customers[0];
        setCustomerId(referenceId(firstCustomer?.id));
        setContactId(referenceId(contactsForCustomer(loaded.references, firstCustomer)[0]?.id));
        setDeliveryMethodId(
          referenceId(activeReferences(loaded.references, "Delivery Methods")[0]?.id),
        );
      })
      .catch((error: unknown) => {
        setContextError(readApiError(error, "Could not load import reference data."));
      });
  }, []);

  const customers = useMemo(
    () => activeReferences(context.references, "JIT Customers"),
    [context.references],
  );
  const selectedCustomer = customers.find((item) => referenceId(item.id) === customerId);
  const contacts = useMemo(
    () => contactsForCustomer(context.references, selectedCustomer),
    [context.references, selectedCustomer],
  );
  const deliveryMethods = useMemo(
    () => activeReferences(context.references, "Delivery Methods"),
    [context.references],
  );
  const lines = payload?.lines ?? [];
  const totalPages = Math.max(1, Math.ceil(lines.length / LINES_PER_PAGE));
  const pageStart = (linePage - 1) * LINES_PER_PAGE;
  const visibleLines = lines.slice(pageStart, pageStart + LINES_PER_PAGE);
  const changedCount =
    draft && payload ? collectCorrections(draft.effective_payload, payload).length : 0;
  const importContextComplete = Boolean(projectId && customerId && contactId && deliveryMethodId);

  if (!can("po.write")) return <AccessDenied what="purchase order intake" />;

  async function parseUpload(file: File) {
    setSourceName(file.name);
    setParsing(true);
    setDraft(null);
    setPayload(null);
    setValidation(null);
    setImportResult(null);
    setLinePage(1);
    try {
      const body = new FormData();
      body.append("file", file);
      const response = await apiFetch("/purchase-orders/parsed/parse", { method: "POST", body });
      if (!response.ok) await throwApiError(response);
      const parsed = (await response.json()) as ParsedPoResponse;
      setDraft(parsed);
      setPayload(clonePayload(parsed.effective_payload));
      toast.success(
        `${file.name} parsed into draft #${parsed.parsed_po_id}. Review all ${parsed.effective_payload.lines?.length ?? 0} lines.`,
      );
    } catch (error) {
      setSourceName(null);
      toast.error(readApiError(error, "Could not parse the purchase-order PDF."));
    } finally {
      setParsing(false);
    }
  }

  function resetDraft() {
    setDraft(null);
    setPayload(null);
    setValidation(null);
    setImportResult(null);
    setSourceName(null);
    setChangeReason("");
    setLinePage(1);
    setUploadKey((value) => value + 1);
  }

  function setHeaderValue(key: string, value: string) {
    setPayload((current) => (current ? { ...current, [key]: value } : current));
    setValidation(null);
  }

  function setLineValue(index: number, key: string, value: string) {
    setPayload((current) => {
      if (!current) return current;
      const nextLines = [...(current.lines ?? [])];
      nextLines[index] = { ...nextLines[index], [key]: value };
      return { ...current, lines: nextLines };
    });
    setValidation(null);
  }

  async function saveAndValidate() {
    if (!draft || !payload) return;
    setValidating(true);
    try {
      const corrections = collectCorrections(draft.effective_payload, payload);
      let reviewedDraft = draft;
      if (corrections.length > 0) {
        const response = await apiFetch(
          `/purchase-orders/parsed/${draft.parsed_po_id}/corrections`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ corrections }),
          },
        );
        if (!response.ok) await throwApiError(response);
        reviewedDraft = (await response.json()) as ParsedPoResponse;
        setDraft(reviewedDraft);
        setPayload(clonePayload(reviewedDraft.effective_payload));
      }
      const response = await apiFetch(`/purchase-orders/parsed/${draft.parsed_po_id}/validate`, {
        method: "POST",
      });
      if (!response.ok) await throwApiError(response);
      const result = (await response.json()) as ValidationResult;
      setValidation(result);
      setPayload(clonePayload(result.effective_payload));
      setDraft({
        ...reviewedDraft,
        status: result.status,
        effective_payload: result.effective_payload,
      });
      if (result.is_valid) toast.success(`Draft #${draft.parsed_po_id} is ready for import.`);
      else toast.error(`Validation found ${result.errors.length} blocking issue(s).`);
    } catch (error) {
      toast.error(readApiError(error, "Could not save and validate the parsed purchase order."));
    } finally {
      setValidating(false);
    }
  }

  async function importDraft() {
    if (!draft || !validation?.is_valid || !importContextComplete) return;
    setConfirmOpen(false);
    setImporting(true);
    try {
      const response = await apiFetch(`/purchase-orders/parsed/${draft.parsed_po_id}/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: Number(projectId),
          customer_id: Number(customerId),
          contact_id: Number(contactId),
          delivery_method_id: Number(deliveryMethodId),
          change_reason: changeReason.trim() || null,
        }),
      });
      if (!response.ok) await throwApiError(response);
      const result = (await response.json()) as ImportResult;
      setImportResult(result);
      setDraft((current) => (current ? { ...current, status: "IMPORTED" } : current));
      void queryClient.invalidateQueries({ queryKey: purchaseOrdersQueryKey });
      toast.success(
        `PO ${display(payload?.["po_number"])} imported with ${result.line_count} line(s).`,
      );
    } catch (error) {
      toast.error(readApiError(error, "Could not import this purchase order."));
    } finally {
      setImporting(false);
    }
  }

  async function downloadSource() {
    if (!draft?.has_source_file) return;
    try {
      const response = await apiFetch(`/purchase-orders/parsed/${draft.parsed_po_id}/source`);
      if (!response.ok) await throwApiError(response);
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = draft.source_file_name ?? `purchase-order-${draft.parsed_po_id}.pdf`;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(readApiError(error, "Could not download the uploaded source file."));
    }
  }

  return (
    <>
      <PageHeader
        title="Purchase order intake"
        subtitle="Choose the PDF first, review every extracted value, then validate and import."
        crumbs={[{ label: "Purchase orders", to: "/purchase-orders" }, { label: "Intake" }]}
        meta={
          <>
            <StatusBadge tone={draft ? "info" : "neutral"}>
              {draft ? `Draft #${draft.parsed_po_id} · ${draft.status}` : "Step 1 · Upload PDF"}
            </StatusBadge>
            {draft && (
              <StatusBadge tone={validation?.is_valid ? "ok" : validation ? "danger" : "warn"}>
                {validation?.is_valid
                  ? "Validated"
                  : validation
                    ? `${validation.errors.length} blocking issue(s)`
                    : `${changedCount} unsaved correction(s)`}
              </StatusBadge>
            )}
          </>
        }
        actions={
          draft ? (
            <>
              <Button variant="outline" size="sm" className="h-8" onClick={resetDraft}>
                <RotateCcw className="size-3.5" /> Choose another PDF
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8"
                disabled={validating || importing || importResult !== null}
                onClick={() => void saveAndValidate()}
              >
                {validating ? "Validating…" : "Save corrections & validate"}
              </Button>
              <Button
                size="sm"
                className="h-8"
                disabled={
                  !validation?.is_valid ||
                  !importContextComplete ||
                  importing ||
                  importResult !== null
                }
                onClick={() => setConfirmOpen(true)}
              >
                {importing ? "Importing…" : "Import PO"}
              </Button>
            </>
          ) : (
            <Button
              variant="outline"
              size="sm"
              className="h-8"
              onClick={() => void navigate({ to: "/purchase-orders" })}
            >
              Cancel
            </Button>
          )
        }
      />

      <div className="space-y-4 p-4">
        {!draft ? (
          <UploadStep
            uploadKey={uploadKey}
            parsing={parsing}
            sourceName={sourceName}
            onName={setSourceName}
            onFile={(file) => void parseUpload(file)}
          />
        ) : importResult ? (
          <ImportSuccess
            draft={draft}
            payload={payload}
            result={importResult}
            onAnother={resetDraft}
            onRegister={() => void navigate({ to: "/purchase-orders" })}
            onDownload={() => void downloadSource()}
          />
        ) : (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="space-y-4">
              <Section
                title="Extracted PO header"
                description="These values come from the uploaded PDF. Changes are saved as correction records."
              >
                <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
                  {HEADER_FIELDS.filter(({ key }) => key in (payload ?? {})).map((field) => (
                    <div key={field.key} className="grid gap-1.5">
                      <Label className="text-xs">
                        {field.label}
                        {"required" in field && field.required && (
                          <span className="ml-1 text-danger">*</span>
                        )}
                      </Label>
                      <Input
                        value={display(payload?.[field.key])}
                        onChange={(event) => setHeaderValue(field.key, event.target.value)}
                        className="h-8 text-xs"
                      />
                      {valueChanged(draft.effective_payload[field.key], payload?.[field.key]) && (
                        <span className="text-xs text-warn">Changed from extracted value</span>
                      )}
                    </div>
                  ))}
                </div>
              </Section>

              <Section
                title={`Extracted line items (${lines.length})`}
                description="Every parsed line is editable and will be imported after validation."
              >
                <LinePagination
                  page={linePage}
                  totalPages={totalPages}
                  start={pageStart}
                  count={visibleLines.length}
                  total={lines.length}
                  onPage={setLinePage}
                />
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-y border-border bg-muted/60">
                        {LINE_FIELDS.map((field) => (
                          <th key={field.key} className="label-caps px-3 py-2 text-left">
                            {field.label}
                            {"required" in field && field.required && (
                              <span className="ml-1 text-danger">*</span>
                            )}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {visibleLines.map((line, pageIndex) => {
                        const index = pageStart + pageIndex;
                        return (
                          <tr
                            key={`${display(line["line_no"])}-${index}`}
                            className="border-b border-border last:border-0 align-top"
                          >
                            {LINE_FIELDS.map((field) => {
                              const editable = field.key in line;
                              const original = draft.effective_payload.lines?.[index]?.[field.key];
                              return (
                                <td key={field.key} className="px-2 py-2">
                                  <Input
                                    value={display(line[field.key])}
                                    disabled={!editable}
                                    onChange={(event) =>
                                      setLineValue(index, field.key, event.target.value)
                                    }
                                    className={`h-8 text-xs ${field.width}`}
                                  />
                                  {valueChanged(original, line[field.key]) && (
                                    <span className="mt-1 block text-[11px] text-warn">
                                      Corrected
                                    </span>
                                  )}
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <LinePagination
                  page={linePage}
                  totalPages={totalPages}
                  start={pageStart}
                  count={visibleLines.length}
                  total={lines.length}
                  onPage={setLinePage}
                />
              </Section>
            </div>

            <div className="space-y-4">
              <Section title="Uploaded source">
                <div className="space-y-3 p-4 text-sm">
                  <div className="flex items-start gap-3 rounded-md border bg-muted/30 p-3">
                    <FileText className="mt-0.5 size-5 shrink-0 text-accent" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{draft.source_file_name ?? sourceName}</p>
                      <p className="text-xs text-muted-foreground">
                        {draft.parser_name ?? "unknown parser"} · Draft #{draft.parsed_po_id}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full"
                    disabled={!draft.has_source_file}
                    onClick={() => void downloadSource()}
                  >
                    <Download className="size-3.5" /> Download original PDF
                  </Button>
                </div>
              </Section>

              <Section
                title="Import destination"
                description="Select the database records used by the imported PO version."
              >
                <div className="space-y-3 p-4">
                  {contextError && (
                    <p className="rounded-md border border-danger/30 bg-danger-soft p-3 text-xs text-danger">
                      {contextError}
                    </p>
                  )}
                  <SelectField
                    label="Project"
                    value={projectId}
                    onChange={setProjectId}
                    options={context.projects
                      .filter((project) => project.status !== "Inactive")
                      .map((project) => ({
                        value: String(project.project_id),
                        label: `${project.project_code} · ${project.name}`,
                      }))}
                  />
                  <SelectField
                    label="Customer"
                    value={customerId}
                    onChange={(value) => {
                      setCustomerId(value);
                      const customer = customers.find((item) => referenceId(item.id) === value);
                      setContactId(
                        referenceId(contactsForCustomer(context.references, customer)[0]?.id),
                      );
                    }}
                    options={customers.map((item) => ({
                      value: referenceId(item.id),
                      label: item.value,
                    }))}
                  />
                  <SelectField
                    label="Customer contact"
                    value={contactId}
                    onChange={setContactId}
                    options={contacts.map((item) => ({
                      value: referenceId(item.id),
                      label: item.value,
                    }))}
                  />
                  <SelectField
                    label="Delivery method"
                    value={deliveryMethodId}
                    onChange={setDeliveryMethodId}
                    options={deliveryMethods.map((item) => ({
                      value: referenceId(item.id),
                      label: item.value,
                    }))}
                  />
                  <div className="grid gap-1.5">
                    <Label className="text-xs">Change reason (optional)</Label>
                    <Input
                      value={changeReason}
                      onChange={(event) => setChangeReason(event.target.value)}
                      className="h-8 text-xs"
                      placeholder="For a revised PO version"
                    />
                  </div>
                </div>
              </Section>
              <ValidationSummary
                validation={validation}
                changedCount={changedCount}
                importContextComplete={importContextComplete}
                onImport={() => setConfirmOpen(true)}
                importing={importing}
              />
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Import validated purchase order"
        confirmLabel={importing ? "Importing…" : "Import PO"}
        disabled={importing || !validation?.is_valid || !importContextComplete}
        onConfirm={() => void importDraft()}
        description={
          <p>
            Import PO <strong>{display(payload?.["po_number"])}</strong>, version{" "}
            <strong>{display(payload?.["version"])}</strong>, with <strong>{lines.length}</strong>{" "}
            line(s). The parsing draft, corrections and original PDF remain linked.
          </p>
        }
      />
    </>
  );
}

function UploadStep({
  uploadKey,
  parsing,
  sourceName,
  onName,
  onFile,
}: {
  uploadKey: number;
  parsing: boolean;
  sourceName: string | null;
  onName: (name: string) => void;
  onFile: (file: File) => void;
}) {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Section
        title="Select the purchase-order document"
        description="Nothing is confirmed or imported until you choose a PDF and complete the review."
      >
        <div className="space-y-4 p-5">
          <FileDropzone
            key={uploadKey}
            accept={[".pdf"]}
            label="Click here to browse your files, or drop a PO PDF"
            hint="Text-based PDF, maximum 20 MB. Scanned PDFs require OCR before upload."
            rejectMessage="Only PDF purchase orders can be uploaded."
            disabled={parsing}
            onAccepted={onName}
            onFileAccepted={onFile}
          />
          <div className="rounded-md border bg-muted/30 p-4 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">Workflow</p>
            <ol className="mt-2 grid gap-2 sm:grid-cols-4">
              <li>1. Choose PDF</li>
              <li>2. Review all lines</li>
              <li>3. Validate corrections</li>
              <li>4. Confirm import</li>
            </ol>
          </div>
          {parsing && (
            <p className="text-center text-sm">
              Parsing <span className="font-medium">{sourceName}</span>…
            </p>
          )}
        </div>
      </Section>
    </div>
  );
}

function LinePagination({
  page,
  totalPages,
  start,
  count,
  total,
  onPage,
}: {
  page: number;
  totalPages: number;
  start: number;
  count: number;
  total: number;
  onPage: (page: number) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
      <p className="text-xs text-muted-foreground">
        Showing {total === 0 ? 0 : start + 1}–{start + count} of {total} lines
      </p>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8"
          disabled={page <= 1}
          aria-label="Previous line page"
          onClick={() => onPage(Math.max(1, page - 1))}
        >
          <ChevronLeft className="size-4" /> Previous
        </Button>
        <span className="min-w-20 text-center text-xs font-medium">
          Page {page} of {totalPages}
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8"
          disabled={page >= totalPages}
          aria-label="Next line page"
          onClick={() => onPage(Math.min(totalPages, page + 1))}
        >
          Next <ChevronRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}

function ValidationSummary({
  validation,
  changedCount,
  importContextComplete,
  onImport,
  importing,
}: {
  validation: ValidationResult | null;
  changedCount: number;
  importContextComplete: boolean;
  onImport: () => void;
  importing: boolean;
}) {
  return (
    <Section title="Validation">
      <div className="space-y-3 p-4 text-sm">
        {!validation ? (
          <div className="flex items-start gap-2 text-muted-foreground">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warn" />
            <p>
              Review the extracted values, then save and validate. {changedCount} correction(s) are
              currently unsaved.
            </p>
          </div>
        ) : validation.is_valid ? (
          <div className="space-y-3">
            <div className="flex items-start gap-2 text-ok">
              <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
              <div>
                <p className="font-medium">Draft is validated!</p>
                <p className="text-xs text-muted-foreground">Next step: Click Import PO below to add it to the Purchase Orders page.</p>
              </div>
            </div>
            <div className="rounded-md border border-info/40 bg-info/10 p-3 text-xs space-y-2">
              <Button
                size="sm"
                className="w-full h-8"
                disabled={!importContextComplete || importing}
                onClick={onImport}
              >
                {importing ? "Importing…" : "Import PO now"}
              </Button>
              {!importContextComplete && (
                <p className="text-[11px] text-danger">
                  Select Project, Customer, Contact, and Delivery Method in the Import Destination panel above before importing.
                </p>
              )}
            </div>
          </div>
        ) : (
          <ul className="space-y-2 text-danger">
            {validation.errors.map((error) => (
              <li key={error} className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" /> {error}
              </li>
            ))}
          </ul>
        )}
        {validation && validation.warnings.length > 0 && (
          <div className="border-t pt-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide">Warnings</p>
            <ul className="space-y-1 text-xs text-warn">
              {validation.warnings.map((warning) => (
                <li key={warning}>• {warning}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Section>
  );
}

function ImportSuccess({
  draft,
  payload,
  result,
  onAnother,
  onRegister,
  onDownload,
}: {
  draft: ParsedPoResponse;
  payload: PoPayload | null;
  result: ImportResult;
  onAnother: () => void;
  onRegister: () => void;
  onDownload: () => void;
}) {
  return (
    <div className="mx-auto max-w-3xl">
      <Section title="Purchase order imported">
        <div className="space-y-5 p-6">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="size-8 shrink-0 text-ok" />
            <div>
              <h2 className="text-lg font-semibold">
                PO {display(payload?.["po_number"])} is stored
              </h2>
              <p className="text-sm text-muted-foreground">
                Version {display(payload?.["version"])} · {result.line_count} line(s) · database PO
                #{result.po_id}
              </p>
            </div>
          </div>
          <dl className="grid gap-3 rounded-md border bg-muted/30 p-4 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs text-muted-foreground">Parsed draft</dt>
              <dd>#{draft.parsed_po_id}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">PO version record</dt>
              <dd>#{result.po_version_id}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">New FGPN masters</dt>
              <dd>{result.created_fgpn_ids.length}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Updated prices</dt>
              <dd>{result.updated_fgpn_price_history_ids.length}</dd>
            </div>
          </dl>
          <div className="flex flex-wrap gap-2">
            <Button onClick={onAnother}>Upload another PO</Button>
            <Button variant="outline" onClick={onDownload} disabled={!draft.has_source_file}>
              <Download className="size-3.5" /> Download original
            </Button>
            <Button variant="outline" onClick={onRegister}>
              Open PO register
            </Button>
          </div>
        </div>
      </Section>
    </div>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="grid gap-1.5">
      <Label className="text-xs">{label} *</Label>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs"
      >
        <option value="">Select {label.toLowerCase()}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

async function loadImportContext(): Promise<ImportContext> {
  const [projectsResponse, referencesResponse] = await Promise.all([
    apiFetch("/projects"),
    apiFetch("/admin/reference-lists"),
  ]);
  if (!projectsResponse.ok) await throwApiError(projectsResponse);
  if (!referencesResponse.ok) await throwApiError(referencesResponse);
  const projects = (await projectsResponse.json()) as { items: ProjectOption[] };
  const references = (await referencesResponse.json()) as { items: ReferenceOption[] };
  return { projects: projects.items, references: references.items };
}

function collectCorrections(original: PoPayload, edited: PoPayload) {
  const corrections: {
    field_path: string;
    original_value: JsonValue;
    corrected_value: JsonValue;
    confirmed: true;
  }[] = [];
  for (const { key } of HEADER_FIELDS) {
    if (!(key in original) || !valueChanged(original[key], edited[key])) continue;
    corrections.push({
      field_path: key,
      original_value: original[key] ?? null,
      corrected_value: edited[key] ?? "",
      confirmed: true,
    });
  }
  const originalLines = original.lines ?? [];
  const editedLines = edited.lines ?? [];
  for (let index = 0; index < originalLines.length; index += 1) {
    const originalLine = originalLines[index];
    const editedLine = editedLines[index];
    if (!originalLine || !editedLine) continue;
    for (const { key } of LINE_FIELDS) {
      if (!(key in originalLine) || !valueChanged(originalLine[key], editedLine[key])) continue;
      corrections.push({
        field_path: `lines[${index}].${key}`,
        original_value: originalLine[key] ?? null,
        corrected_value: editedLine[key] ?? "",
        confirmed: true,
      });
    }
  }
  return corrections;
}

function valueChanged(original: JsonValue | undefined, edited: JsonValue | undefined) {
  return JSON.stringify(original ?? null) !== JSON.stringify(edited ?? null);
}

function clonePayload(payload: PoPayload): PoPayload {
  return JSON.parse(JSON.stringify(payload)) as PoPayload;
}

function display(value: JsonValue | undefined): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function activeReferences(references: ReferenceOption[], list: string) {
  return references.filter((item) => item.list === list && item.active);
}

function contactsForCustomer(references: ReferenceOption[], customer?: ReferenceOption) {
  if (!customer) return [];
  return activeReferences(references, "Contact Names").filter(
    (item) => item.detail === customer.value,
  );
}

function referenceId(id?: string) {
  return id?.split(":").at(-1) ?? "";
}
