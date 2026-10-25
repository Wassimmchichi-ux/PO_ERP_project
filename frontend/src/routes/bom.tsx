import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState, useEffect, Fragment } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileDiff,
  GitCompareArrows,
  History,
  Upload,
  FileSpreadsheet,
  Download,
  ChevronRight,
  ChevronLeft,
  Maximize2,
  Minimize2,
  Search,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader, Section } from "@/components/erp/PageHeader";
import { StatusBadge } from "@/components/erp/StatusBadge";
import { AccessDenied, EmptyState } from "@/components/erp/EmptyState";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSession } from "@/lib/erp/session";
import { nf } from "@/lib/erp/format";
import { pageTitle } from "@/lib/erp/appInfo";
import { apiFetch, readApiError, throwApiError } from "@/lib/erp/api";
import {
  fetchPurchaseOrders,
  purchaseOrdersQueryKey,
} from "@/lib/erp/purchaseOrderApi";

export interface BomMaterialLine {
  source_row_number: number;
  material_part_number: string;
  material_description?: string | null;
  cover_revision?: string | null;
  cover_pn?: string | null;
  cover_description?: string | null;
  part_type?: string | null;
  coefficient: number;
  quantity_tpdm?: number | null;
  total_quantity?: number | null;
  unit?: string | null;
  source_unit?: string | null;
  total_sqm?: number | null;
}

export interface BomVersionItem {
  id: number;
  fgpn_id: number;
  finished_good_part_number: string;
  version: number;
  development_level?: string | null;
  source_filename: string;
  uploaded_by?: string | null;
  source_reported_by?: string | null;
  source_report_date?: string | null;
  source_report_time?: string | null;
  material_row_count: number;
  is_current: boolean;
  notes?: string | null;
  project_id?: number | null;
  project_code?: string | null;
  material_lines: BomMaterialLine[];
}

export interface ApiBomUploadResult {
  uploaded_count: number;
  versions: BomVersionItem[];
}

export const bomsQueryKey = ["boms"] as const;

export async function fetchBoms(
  projectId?: number | null,
  signal?: AbortSignal,
): Promise<BomVersionItem[]> {
  const query = projectId ? `?project_id=${projectId}` : "";
  const response = await apiFetch(`/boms${query}`, signal ? { signal } : {});
  if (!response.ok) await throwApiError(response);
  return (await response.json()) as BomVersionItem[];
}

async function uploadBomWorkbooks(
  files: File[],
  uploadedBy: string,
  projectId?: number | null,
): Promise<ApiBomUploadResult> {
  const body = new FormData();
  files.forEach((file) => body.append("files", file));
  body.append("uploaded_by", uploadedBy);
  if (projectId) {
    body.append("project_id", String(projectId));
  }
  const response = await apiFetch("/boms/upload", { method: "POST", body });
  if (!response.ok) await throwApiError(response);
  return (await response.json()) as ApiBomUploadResult;
}

type NumericCompareKey = "coefficient" | "quantityTpdm" | "totalQty" | "totalSqm";

const NUMERIC_COMPARE_COLUMNS: { key: NumericCompareKey; label: string }[] = [
  { key: "coefficient", label: "Coefficient" },
  { key: "quantityTpdm", label: "Quantity TPDM" },
  { key: "totalQty", label: "Total qty" },
  { key: "totalSqm", label: "Total sqm" },
];

function formatDelta(value: number) {
  if (value === 0) return "0";
  return `${value > 0 ? "+" : ""}${nf.format(value)}`;
}

function deltaTone(value: number) {
  if (value > 0) return "text-ok";
  if (value < 0) return "text-danger";
  return "text-muted-foreground";
}

export const Route = createFileRoute("/bom")({
  head: () => ({
    meta: [
      { title: pageTitle("Bill of Material") },
      {
        name: "description",
        content:
          "Project bills of material: uploaded Excel Source DATA versions and FGPN-to-material usage used by launch simulation.",
      },
      { property: "og:title", content: pageTitle("Bill of Material") },
    ],
  }),
  component: BomPage,
});

// ─── Reusable material lines table ───────────────────────────────────────────
function MaterialLinesTable({ lines }: { lines: BomMaterialLine[] }) {
  if (lines.length === 0)
    return <p className="py-4 text-center text-xs text-muted-foreground">No material lines extracted.</p>;
  return (
    <div className="max-h-[300px] overflow-auto rounded border border-border custom-scrollbar">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-muted/90 backdrop-blur-xs font-semibold text-muted-foreground">
          <tr className="border-b border-border">
            <th className="px-3 py-2 text-left font-mono">Pos</th>
            <th className="px-3 py-2 text-left font-mono">Material PN</th>
            <th className="px-3 py-2 text-left">Description</th>
            <th className="px-3 py-2 text-center">Type</th>
            <th className="px-3 py-2 text-right">Coeff</th>
            <th className="px-3 py-2 text-right">Qty TPDM</th>
            <th className="px-3 py-2 text-right">Total Qty</th>
            <th className="px-3 py-2 text-right">Total SQM</th>
            <th className="px-3 py-2 text-left">Unit</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((l) => (
            <tr
              key={`${l.source_row_number}-${l.material_part_number}`}
              className="border-b border-border/60 last:border-0 hover:bg-muted/30"
            >
              <td className="px-3 py-1.5 font-mono text-muted-foreground">{l.source_row_number}</td>
              <td className="px-3 py-1.5 font-mono font-medium text-foreground">{l.material_part_number}</td>
              <td className="px-3 py-1.5 text-muted-foreground max-w-[200px] truncate">{l.material_description ?? "—"}</td>
              <td className="px-3 py-1.5 text-center">
                <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-bold ${
                  l.part_type === "M"
                    ? "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300"
                    : "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300"
                }`}>
                  {l.part_type ?? "—"}
                </span>
              </td>
              <td className="px-3 py-1.5 text-right font-mono">{l.coefficient}</td>
              <td className="px-3 py-1.5 text-right font-mono">{l.quantity_tpdm != null ? String(l.quantity_tpdm) : "—"}</td>
              <td className="px-3 py-1.5 text-right font-mono">{l.total_quantity != null ? String(l.total_quantity) : "—"}</td>
              <td className="px-3 py-1.5 text-right font-mono font-semibold text-foreground">
                {l.total_sqm != null ? Number(l.total_sqm).toFixed(4) : "—"}
              </td>
              <td className="px-3 py-1.5 font-mono text-muted-foreground">{l.unit ?? l.source_unit ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── BOM Status badge ─────────────────────────────────────────────────────────
function BomStatusBadge({ hasBom, version }: { hasBom: boolean; version?: number | undefined }) {
  if (hasBom) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium bg-white text-emerald-600 border border-emerald-300 dark:bg-background dark:text-emerald-400 dark:border-emerald-800 whitespace-nowrap shadow-2xs">
        <span className="size-1.5 rounded-full bg-emerald-500 shrink-0" />
        v{version ?? 1} Uploaded
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium bg-white text-slate-500 border border-slate-200 dark:bg-background dark:text-slate-400 dark:border-slate-700 whitespace-nowrap shadow-2xs">
      <span className="size-1.5 rounded-full bg-slate-400 shrink-0" />
      No BOM
    </span>
  );
}

function BomPage() {
  const { can, user } = useSession();
  const queryClient = useQueryClient();

  const [selectedPoNumbers, setSelectedPoNumbers] = useState<Set<string>>(() => new Set());
  const [fgpnFilter, setFgpnFilter] = useState("");
  const [bomFilter, setBomFilter] = useState("");
  const [compareFgpn, setCompareFgpn] = useState<string | null>(null);
  const [firstVersionId, setFirstVersionId] = useState<string>("");
  const [secondVersionId, setSecondVersionId] = useState<string>("");
  const [uploading, setUploading] = useState(false);
  const [selectedBomId, setSelectedBomId] = useState<number | null>(null);
  const [expandedFgpn, setExpandedFgpn] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 15;

  // Reset page when filter changes
  useEffect(() => { setPage(1); }, [fgpnFilter, selectedPoNumbers]);

  // Esc to close fullscreen
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setIsFullscreen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  async function handleDownloadBom(bomId: number, filename?: string) {
    try {
      const res = await apiFetch(`/boms/${bomId}/download`);
      if (!res.ok) await throwApiError(res);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename || `BOM_${bomId}.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success(`Downloaded ${filename || `BOM_${bomId}.xlsx`}`);
    } catch (err) {
      toast.error(readApiError(err, "Failed to download BOM file."));
    }
  }

  const bomsQuery = useQuery({
    queryKey: bomsQueryKey,
    queryFn: ({ signal }) => fetchBoms(undefined, signal),
  });

  const purchaseOrdersQuery = useQuery({
    queryKey: purchaseOrdersQueryKey,
    queryFn: ({ signal }) => fetchPurchaseOrders(signal),
  });

  const boms = bomsQuery.data ?? [];
  const purchaseOrders = purchaseOrdersQuery.data?.items ?? [];

  const currentBom = useMemo(() => {
    if (boms.length === 0) return null;
    if (selectedBomId != null) {
      const match = boms.find((b) => b.id === selectedBomId);
      if (match) return match;
    }
    return boms.find((b) => b.is_current) ?? boms[0];
  }, [boms, selectedBomId]);

  const poFilterOptions = useMemo(() => {
    return purchaseOrders.map((po) => ({
      poNumber: po.po_number,
      label: `${po.po_number}${po.delivery_week ? ` (${po.delivery_week})` : ""}`,
      status: po.status,
      fgpnCount: po.fgpn_codes.length,
      fgpnCodes: po.fgpn_codes,
      projectId: po.project_id,
    }));
  }, [purchaseOrders]);

  useMemo(() => {
    if (selectedPoNumbers.size === 0 && poFilterOptions.length > 0) {
      setSelectedPoNumbers(new Set(poFilterOptions.map((po) => po.poNumber)));
    }
  }, [poFilterOptions, selectedPoNumbers.size]);

  const fgpnRows = useMemo(() => {
    const q = fgpnFilter.trim().toLowerCase();
    const bomsByFgpn = new Map<string, BomVersionItem[]>();
    boms.forEach((bom) => {
      const list = bomsByFgpn.get(bom.finished_good_part_number) ?? [];
      list.push(bom);
      bomsByFgpn.set(bom.finished_good_part_number, list);
    });
    const poByFgpn = new Map<string, Set<string>>();
    purchaseOrders.forEach((po) => {
      po.fgpn_codes.forEach((code) => {
        const set = poByFgpn.get(code) ?? new Set();
        set.add(po.po_number);
        poByFgpn.set(code, set);
      });
    });
    const allFgpnCodes = new Set<string>([...bomsByFgpn.keys(), ...poByFgpn.keys()]);

    const rows: Array<{
      fgpn: string;
      description: string;
      poNumberList: string[];
      poNumbers: string;
      hasBom: boolean;
      currentBom?: BomVersionItem | undefined;
      bomLineCount: number;
      versionNumber?: number | undefined;
      projectId?: number | null;
    }> = [];

    allFgpnCodes.forEach((code) => {
      const fgpnBoms = bomsByFgpn.get(code) ?? [];
      const activeBom = fgpnBoms.find((b) => b.is_current) ?? fgpnBoms[0];
      const poNumbers = Array.from(poByFgpn.get(code) ?? []);
      const linkedPo = purchaseOrders.find((po) => po.fgpn_codes.includes(code));
      const effectiveProjectId = activeBom?.project_id ?? linkedPo?.project_id ?? null;
      rows.push({
        fgpn: code,
        description: activeBom?.notes ?? "Finished good part",
        poNumberList: poNumbers,
        poNumbers: poNumbers.join(", ") || "—",
        hasBom: fgpnBoms.length > 0,
        currentBom: activeBom,
        bomLineCount: activeBom?.material_lines.length ?? activeBom?.material_row_count ?? 0,
        versionNumber: activeBom?.version,
        projectId: effectiveProjectId,
      });
    });

    return rows
      .filter((row) => {
        if (selectedPoNumbers.size === 0) return true;
        if (row.poNumberList.length === 0) return true;
        return row.poNumberList.some((po) => selectedPoNumbers.has(po));
      })
      .filter((row) => {
        if (!q) return true;
        return `${row.fgpn} ${row.description} ${row.poNumbers}`.toLowerCase().includes(q);
      });
  }, [boms, purchaseOrders, selectedPoNumbers, fgpnFilter]);

  // Filtered BOM versions for sidebar
  const filteredBoms = useMemo(() => {
    if (!bomFilter.trim()) return boms;
    const q = bomFilter.trim().toLowerCase();
    return boms.filter(
      (b) =>
        b.finished_good_part_number.toLowerCase().includes(q) ||
        b.source_filename.toLowerCase().includes(q) ||
        (b.source_reported_by ?? "").toLowerCase().includes(q),
    );
  }, [boms, bomFilter]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(fgpnRows.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const paginatedRows = useMemo(
    () => fgpnRows.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE),
    [fgpnRows, safePage],
  );

  async function handleBomUpload(files: File[], targetProjectId?: number | null) {
    if (files.length === 0) return;
    setUploading(true);
    try {
      const selectedPo = purchaseOrders.find((po) => selectedPoNumbers.has(po.po_number));
      const fallbackProjectId =
        targetProjectId ??
        currentBom?.project_id ??
        selectedPo?.project_id ??
        purchaseOrders[0]?.project_id ??
        null;
      const result = await uploadBomWorkbooks(files, user.username, fallbackProjectId);
      toast.success(
        `${result.uploaded_count} BOM version${result.uploaded_count === 1 ? "" : "s"} parsed and uploaded to database.`,
      );
      await queryClient.invalidateQueries({ queryKey: bomsQueryKey });
      await queryClient.refetchQueries({ queryKey: bomsQueryKey });
      void queryClient.invalidateQueries({ queryKey: ["simulation-options"] });
    } catch (error) {
      toast.error(readApiError(error, "Could not upload the BOM workbook(s) to the backend."));
    } finally {
      setUploading(false);
    }
  }

  const compareVersions = useMemo(() => {
    if (!compareFgpn) return [];
    return boms
      .filter((b) => b.finished_good_part_number === compareFgpn)
      .sort((a, b) => a.version - b.version);
  }, [boms, compareFgpn]);

  const compareResult = useMemo(() => {
    if (compareVersions.length < 2 && !firstVersionId && !secondVersionId) return null;
    const firstVersion =
      compareVersions.find((v) => String(v.id) === firstVersionId) ?? compareVersions[0];
    const secondVersion =
      compareVersions.find((v) => String(v.id) === secondVersionId) ??
      compareVersions[compareVersions.length - 1];
    if (!firstVersion || !secondVersion || !compareFgpn) return null;
    const firstLines = firstVersion.material_lines;
    const secondLines = secondVersion.material_lines;
    const firstByMaterial = new Map(firstLines.map((l) => [l.material_part_number, l]));
    const secondByMaterial = new Map(secondLines.map((l) => [l.material_part_number, l]));
    const allMaterials = Array.from(
      new Set([...firstByMaterial.keys(), ...secondByMaterial.keys()]),
    ).sort();
    const changes = allMaterials.map((matPn) => {
      const first = firstByMaterial.get(matPn);
      const second = secondByMaterial.get(matPn);
      const firstVals = first
        ? {
            coefficient: Number(first.coefficient),
            quantityTpdm: Number(first.quantity_tpdm ?? 0),
            totalQty: Number(first.total_quantity ?? 0),
            totalSqm: Number(first.total_sqm ?? 0),
          }
        : undefined;
      const secondVals = second
        ? {
            coefficient: Number(second.coefficient),
            quantityTpdm: Number(second.quantity_tpdm ?? 0),
            totalQty: Number(second.total_quantity ?? 0),
            totalSqm: Number(second.total_sqm ?? 0),
          }
        : undefined;
      const numericDeltas = NUMERIC_COMPARE_COLUMNS.reduce(
        (acc, col) => {
          acc[col.key] = (secondVals?.[col.key] ?? 0) - (firstVals?.[col.key] ?? 0);
          return acc;
        },
        {} as Record<NumericCompareKey, number>,
      );
      const hasNumericChange = NUMERIC_COMPARE_COLUMNS.some((col) => numericDeltas[col.key] !== 0);
      let change: "Added" | "Removed" | "Changed" | "Unchanged";
      if (!first && second) change = "Added";
      else if (first && !second) change = "Removed";
      else if (hasNumericChange) change = "Changed";
      else change = "Unchanged";
      return {
        materialPartNumber: matPn,
        materialDescription: second?.material_description ?? first?.material_description ?? "—",
        partType: second?.part_type ?? first?.part_type ?? "—",
        unit: second?.unit ?? first?.unit ?? "—",
        firstVals,
        secondVals,
        numericDeltas,
        change,
      };
    });
    return {
      fgpn: compareFgpn,
      firstVersion,
      secondVersion,
      firstLineCount: firstLines.length,
      secondLineCount: secondLines.length,
      added: changes.filter((c) => c.change === "Added").length,
      removed: changes.filter((c) => c.change === "Removed").length,
      changed: changes.filter((c) => c.change === "Changed").length,
      unchanged: changes.filter((c) => c.change === "Unchanged").length,
      changes,
    };
  }, [compareFgpn, compareVersions, firstVersionId, secondVersionId]);

  if (!can("bom.view")) return <AccessDenied what="bills of material" />;
  const canUpload = can("bom.write");

  // ─── Coverage table rows renderer ────────────────────────────────────────
  function CoverageRows({ rows, colSpan }: { rows: typeof fgpnRows; colSpan: number }) {
    return (
      <>
        {rows.map((row) => {
          const isExpanded = expandedFgpn === row.fgpn;
          return (
            <Fragment key={row.fgpn}>
              <tr
                className={`border-b border-border transition-colors cursor-pointer select-none ${
                  isExpanded
                    ? "bg-primary/5"
                    : row.hasBom
                    ? "hover:bg-muted/30"
                    : "hover:bg-muted/20"
                }`}
                onClick={() => {
                  setExpandedFgpn(isExpanded ? null : row.fgpn);
                  if (row.currentBom) setSelectedBomId(row.currentBom.id);
                }}
              >
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <ChevronRight
                      className={`size-3.5 shrink-0 text-muted-foreground transition-transform duration-150 ${isExpanded ? "rotate-90 text-primary" : ""}`}
                    />
                    <span className="font-mono text-xs font-semibold text-foreground">{row.fgpn}</span>
                  </div>
                </td>
                <td className="px-4 py-2.5 text-xs text-muted-foreground truncate max-w-xs">{row.description}</td>
                <td className="px-4 py-2.5 text-xs font-mono text-muted-foreground">{row.poNumbers}</td>
                <td className="px-4 py-2.5 text-center">
                  <BomStatusBadge hasBom={row.hasBom} version={row.versionNumber ?? undefined} />
                </td>
                <td className="px-4 py-2.5 text-center" onClick={(e) => e.stopPropagation()}>
                  <div className="flex items-center justify-center gap-1.5">
                    <Button
                      type="button"
                      variant={compareFgpn === row.fgpn ? "default" : "outline"}
                      size="sm"
                      className="h-7 gap-1 text-xs"
                      disabled={!row.hasBom}
                      onClick={(e) => {
                        e.stopPropagation();
                        setCompareFgpn(row.fgpn);
                      }}
                    >
                      <GitCompareArrows className="size-3" />
                      Compare
                    </Button>
                  </div>
                </td>
                <td className="px-4 py-2.5 text-right text-xs">
                  {row.hasBom ? (
                    <span className="font-semibold text-foreground">{row.bomLineCount}</span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
              </tr>

              {/* Expanded drawer */}
              {isExpanded && (
                <tr className="bg-muted/10 border-b border-border">
                  <td colSpan={colSpan} className="px-4 py-4">
                    {row.hasBom && row.currentBom ? (
                      <div className="rounded-lg border border-border bg-card shadow-xs overflow-hidden">
                        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 bg-muted/30 border-b border-border">
                          <div className="flex items-center gap-3">
                            <FileSpreadsheet className="size-5 shrink-0 text-emerald-600" />
                            <div>
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-sm font-semibold font-mono text-foreground">{row.fgpn}</span>
                                <span className="rounded-full bg-white border border-emerald-300 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-background dark:text-emerald-300 dark:border-emerald-800">
                                  v{row.currentBom.version} · {row.currentBom.material_lines.length} lines
                                </span>
                              </div>
                              <p className="text-[11px] text-muted-foreground mt-0.5 font-mono">
                                {row.currentBom.source_filename}
                                {row.currentBom.source_reported_by && (
                                  <span className="font-sans"> · By {row.currentBom.source_reported_by}</span>
                                )}
                                {row.currentBom.source_report_date && (
                                  <span className="font-sans"> · {row.currentBom.source_report_date}</span>
                                )}
                              </p>
                            </div>
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="h-8 gap-1.5 text-xs shrink-0"
                            onClick={(e) => {
                              e.stopPropagation();
                              void handleDownloadBom(row.currentBom!.id, row.currentBom!.source_filename);
                            }}
                          >
                            <Download className="size-3.5" />
                            Download original Excel
                          </Button>
                        </div>
                        <div className="p-3">
                          <MaterialLinesTable lines={row.currentBom.material_lines} />
                        </div>
                      </div>
                    ) : (
                      <div className="rounded-lg border border-dashed border-border bg-card p-4 shadow-xs">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div className="flex items-center gap-3">
                            <FileSpreadsheet className="size-5 shrink-0 text-muted-foreground" />
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-semibold font-mono text-foreground">{row.fgpn}</span>
                                <span className="rounded-full bg-white border border-slate-200 px-2 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-background dark:text-slate-400">
                                  No BOM
                                </span>
                              </div>
                              <p className="text-xs text-muted-foreground mt-0.5">
                                No bill of materials uploaded for this finished good part number yet.
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="h-8 gap-1.5 text-xs shrink-0"
                              onClick={(e) => {
                                e.stopPropagation();
                                const link = document.createElement("a");
                                link.href = `/sample_mbom/MBOM_${row.fgpn}.xlsx`;
                                link.download = `MBOM_${row.fgpn}.xlsx`;
                                document.body.appendChild(link);
                                link.click();
                                document.body.removeChild(link);
                              }}
                            >
                              <Download className="size-3.5" />
                              Download BOM ({row.fgpn})
                            </Button>
                            {canUpload && (
                              <>
                                <input
                                  id={`upload-bom-${row.fgpn}`}
                                  type="file"
                                  accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                  className="sr-only"
                                  disabled={uploading}
                                  onChange={(e) => {
                                    const files = Array.from(e.currentTarget.files ?? []);
                                    void handleBomUpload(files, row.projectId);
                                    e.currentTarget.value = "";
                                  }}
                                />
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="default"
                                  className="h-8 gap-1.5 text-xs shrink-0"
                                  disabled={uploading}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    document.getElementById(`upload-bom-${row.fgpn}`)?.click();
                                  }}
                                >
                                  <Upload className="size-3.5" />
                                  {uploading ? "Uploading…" : "Upload BOM"}
                                </Button>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </td>
                </tr>
              )}
            </Fragment>
          );
        })}
      </>
    );
  }

  // ─── Pagination bar ───────────────────────────────────────────────────────
  function PaginationBar() {
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-4 py-2 text-xs bg-muted/20 shrink-0">
        <span className="text-muted-foreground">
          {fgpnRows.length === 0 ? (
            "No results"
          ) : (
            <>
              <span className="font-medium text-foreground">{(safePage - 1) * PAGE_SIZE + 1}</span>
              {" – "}
              <span className="font-medium text-foreground">{Math.min(safePage * PAGE_SIZE, fgpnRows.length)}</span>
              {" of "}
              <span className="font-medium text-foreground">{fgpnRows.length}</span>
              {" parts"}
            </>
          )}
        </span>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-6 px-2 text-xs"
            disabled={safePage <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            <ChevronLeft className="size-3" />
          </Button>
          <span className="px-2 text-muted-foreground">
            <span className="font-medium text-foreground">{safePage}</span>
            {" / "}
            <span className="font-medium text-foreground">{totalPages}</span>
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-6 px-2 text-xs"
            disabled={safePage >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            <ChevronRight className="size-3" />
          </Button>
        </div>
      </div>
    );
  }

  // ─── Coverage table header ─────────────────────────────────────────────────
  function CoverageHeader() {
    return (
      <thead className="sticky top-0 z-10">
        <tr className="border-b border-border bg-muted/70">
          <th className="label-caps px-4 py-2.5 text-left">FGPN</th>
          <th className="label-caps px-4 py-2.5 text-left">Description</th>
          <th className="label-caps px-4 py-2.5 text-left">PO</th>
          <th className="label-caps px-4 py-2.5 text-center">BOM Status</th>
          <th className="label-caps px-4 py-2.5 text-center">Actions</th>
          <th className="label-caps px-4 py-2.5 text-right">Lines</th>
        </tr>
      </thead>
    );
  }

  return (
    <>
      <PageHeader
        title="Bill of material"
        subtitle="Upload Excel BOM workbooks (Source DATA sheet), inspect extracted material lines, and compare versions."
        crumbs={[{ label: "Planning" }, { label: "Bill of material" }]}
        actions={
          canUpload ? (
            <>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 gap-1.5 text-xs"
                disabled={uploading}
                onClick={() => document.getElementById("bom-header-upload")?.click()}
              >
                <Upload className="size-3.5" />
                {uploading ? "Uploading & parsing…" : "Upload BOM Excel"}
              </Button>
              <input
                id="bom-header-upload"
                type="file"
                multiple
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                className="sr-only"
                disabled={uploading}
                onChange={(e) => {
                  const files = Array.from(e.currentTarget.files ?? []);
                  void handleBomUpload(files);
                  e.currentTarget.value = "";
                }}
              />
            </>
          ) : undefined
        }
      />

      <div className="grid gap-4 p-4 xl:grid-cols-[340px_minmax(0,1fr)]">
        {/* ── Left column ── */}
        <div className="space-y-4">
          {/* PO filter */}
          <Section title="PO filter" description="Filter FGPNs by linked purchase orders.">
            {poFilterOptions.length === 0 ? (
              <EmptyState title="No POs loaded" />
            ) : (
              <>
                <div className="flex items-center justify-between border-b border-border px-4 py-2">
                  <span className="text-xs text-muted-foreground">
                    {selectedPoNumbers.size}/{poFilterOptions.length} selected
                  </span>
                  <div className="flex items-center gap-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-xs"
                      onClick={() =>
                        setSelectedPoNumbers(new Set(poFilterOptions.map((po) => po.poNumber)))
                      }
                    >
                      All
                    </Button>
                    <span className="text-border">|</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-xs text-muted-foreground"
                      onClick={() => setSelectedPoNumbers(new Set())}
                    >
                      Clear
                    </Button>
                  </div>
                </div>
                <div className="max-h-[260px] overflow-y-auto overscroll-contain p-2 custom-scrollbar [scrollbar-gutter:stable]">
                  <div className="space-y-1.5">
                    {poFilterOptions.map((po) => (
                      <label
                        key={po.poNumber}
                        className="flex cursor-pointer items-center gap-3 rounded-md border border-border bg-muted/10 px-3 py-2 hover:bg-muted/40 transition-colors"
                      >
                        <Checkbox
                          checked={selectedPoNumbers.has(po.poNumber)}
                          onCheckedChange={(checked) => {
                            setSelectedPoNumbers((prev) => {
                              const next = new Set(prev);
                              if (checked) next.add(po.poNumber);
                              else next.delete(po.poNumber);
                              return next;
                            });
                          }}
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate num text-xs font-semibold">{po.label}</span>
                          <span className="block text-[11px] text-muted-foreground">
                            {po.fgpnCount} FGPN line{po.fgpnCount === 1 ? "" : "s"}
                          </span>
                        </span>
                        <StatusBadge tone="neutral">{po.status}</StatusBadge>
                      </label>
                    ))}
                  </div>
                </div>
              </>
            )}
          </Section>

          {/* Database BOM Versions */}
          <Section
            title="Database BOM Versions"
            description="Select a BOM version to inspect its details."
          >
            {boms.length === 0 ? (
              <div className="p-4 text-center text-xs text-muted-foreground">
                No BOMs uploaded yet. Click "Upload BOM Excel" to import a workbook.
              </div>
            ) : (
              <>
                {/* Search filter */}
                <div className="border-b border-border p-2">
                  <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3 text-muted-foreground" />
                    <Input
                      value={bomFilter}
                      onChange={(e) => setBomFilter(e.target.value)}
                      placeholder="Filter by FGPN, filename…"
                      className="h-7 pl-7 text-xs bg-background"
                    />
                  </div>
                </div>
                {filteredBoms.length === 0 ? (
                  <p className="p-4 text-center text-xs text-muted-foreground">No matching versions.</p>
                ) : (
                  <div className="max-h-[300px] overflow-y-auto overscroll-contain p-2 space-y-1.5 custom-scrollbar">
                    {filteredBoms.map((bom) => {
                      const isSelected = currentBom?.id === bom.id;
                      return (
                        <div
                          key={bom.id}
                          onClick={() => setSelectedBomId(bom.id)}
                          className={`cursor-pointer rounded-md border p-2.5 transition-colors ${
                            isSelected
                              ? "border-primary/40 bg-primary/5"
                              : "border-border bg-muted/10 hover:bg-muted/30"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-mono text-xs font-bold text-foreground">
                              {bom.finished_good_part_number}
                            </span>
                            {bom.is_current ? (
                              <StatusBadge tone="ok">v{bom.version} · Current</StatusBadge>
                            ) : (
                              <StatusBadge tone="neutral">v{bom.version}</StatusBadge>
                            )}
                          </div>
                          <p className="text-[11px] text-muted-foreground truncate mt-1 font-mono">
                            {bom.source_filename}
                          </p>
                          <div className="flex items-center justify-between text-[10px] text-muted-foreground mt-1">
                            <span>{bom.material_row_count} lines</span>
                            {bom.source_reported_by && <span>By {bom.source_reported_by}</span>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </Section>
        </div>

        {/* ── Right column ── */}
        <div className="space-y-4">
          {/* FGPN BOM Coverage Table */}
          <Section
            title="FGPN BOM coverage"
            description="Bulk uploads can include multiple workbooks and multiple FGPNs per workbook."
            actions={
              <div className="flex items-center gap-2">
                {/* Fullscreen toggle — subtle grey icon top-left of title area */}
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground hover:bg-muted"
                  title="Expand to full screen (Esc to close)"
                  onClick={() => setIsFullscreen(true)}
                >
                  <Maximize2 className="size-3.5" />
                </Button>
                {/* Bulk upload */}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 gap-1.5 text-xs"
                  disabled={uploading || !canUpload}
                  onClick={() => document.getElementById("bom-bulk-upload")?.click()}
                >
                  <Upload className="size-3.5" />
                  {uploading ? "Uploading…" : "Bulk upload"}
                </Button>
                <input
                  id="bom-bulk-upload"
                  type="file"
                  multiple
                  accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  className="sr-only"
                  disabled={uploading || !canUpload}
                  onChange={(event) => {
                    const files = Array.from(event.currentTarget.files ?? []);
                    void handleBomUpload(files);
                    event.currentTarget.value = "";
                  }}
                />
                {/* Filter */}
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3 text-muted-foreground" />
                  <Input
                    value={fgpnFilter}
                    onChange={(e) => setFgpnFilter(e.target.value)}
                    placeholder="Filter FGPN or PO…"
                    className="h-7 w-52 pl-7 text-xs bg-background"
                  />
                </div>
              </div>
            }
          >
            {fgpnRows.length === 0 ? (
              <EmptyState title="No FGPN matches found in purchase orders or database" />
            ) : (
              <>
                <div className="overflow-x-auto custom-scrollbar">
                  <table className="w-full min-w-[720px] text-sm">
                    <CoverageHeader />
                    <tbody>
                      <CoverageRows rows={paginatedRows} colSpan={6} />
                    </tbody>
                  </table>
                </div>
                <PaginationBar />
              </>
            )}
          </Section>
        </div>

        {/* ── Full-width BOM comparison section ── */}
        <div className="xl:col-span-2">
          <Section
            title="BOM comparison"
            description="Compare one FGPN between two stored BOM versions."
          >
            {!compareResult ? (
              <div className="flex min-h-[180px] items-center justify-center border-t border-border p-8 text-center">
                <div className="space-y-2">
                  <div className="mx-auto grid size-10 place-items-center rounded-md border border-border bg-muted/40 text-muted-foreground">
                    <GitCompareArrows className="size-5" />
                  </div>
                  <p className="text-sm font-semibold text-foreground">Select an FGPN to compare</p>
                  <p className="max-w-md text-xs text-muted-foreground">
                    Use the Compare button in the table above to inspect what changed in the BOM for
                    one finished good part number.
                  </p>
                </div>
              </div>
            ) : (
              <div className="border-t border-border">
                <div className="grid gap-3 p-4 lg:grid-cols-[300px_minmax(0,1fr)]">
                  <div className="space-y-3 lg:order-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                        <FileDiff className="size-4 text-info" />
                        {compareResult.fgpn}
                      </div>
                      <StatusBadge tone="info">
                        v{compareResult.firstVersion.version} → v{compareResult.secondVersion.version}
                      </StatusBadge>
                    </div>

                    <div className="grid gap-2 sm:grid-cols-4">
                      <div className="rounded-md border border-ok/25 bg-ok-soft p-3">
                        <p className="label-caps">Added</p>
                        <p className="num mt-1 text-lg font-bold text-ok">{compareResult.added}</p>
                      </div>
                      <div className="rounded-md border border-danger/25 bg-danger-soft p-3">
                        <p className="label-caps">Removed</p>
                        <p className="num mt-1 text-lg font-bold text-danger">{compareResult.removed}</p>
                      </div>
                      <div className="rounded-md border border-warn/30 bg-warn-soft p-3">
                        <p className="label-caps">Changed</p>
                        <p className="num mt-1 text-lg font-bold text-warn">{compareResult.changed}</p>
                      </div>
                      <div className="rounded-md border border-border bg-muted/30 p-3">
                        <p className="label-caps">Unchanged</p>
                        <p className="num mt-1 text-lg font-bold text-foreground">{compareResult.unchanged}</p>
                      </div>
                    </div>

                    {compareResult.changes.length === 0 ? (
                      <div className="rounded-md border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
                        No BOM lines exist for this FGPN in the selected versions.
                      </div>
                    ) : (
                      <div className="max-h-[260px] overflow-auto overscroll-contain rounded-md border border-border custom-scrollbar [scrollbar-gutter:stable]">
                        <table className="w-full min-w-[860px] text-sm">
                          <thead className="sticky top-0 z-10">
                            <tr className="border-b border-border bg-muted/70 shadow-sm">
                              <th className="label-caps px-4 py-2 text-left">Material PN</th>
                              <th className="label-caps px-4 py-2 text-left">Description</th>
                              <th className="label-caps px-4 py-2 text-left">Part type</th>
                              <th className="label-caps px-4 py-2 text-left">Unit</th>
                              {NUMERIC_COMPARE_COLUMNS.map((column) => (
                                <th key={column.key} className="label-caps px-4 py-2 text-right">
                                  Δ {column.label}
                                </th>
                              ))}
                              <th className="label-caps px-4 py-2 text-center">Change</th>
                            </tr>
                          </thead>
                          <tbody>
                            {compareResult.changes.map((change) => (
                              <tr key={change.materialPartNumber} className="border-b border-border last:border-0">
                                <td className="num px-4 py-2 font-medium">{change.materialPartNumber}</td>
                                <td className="px-4 py-2 text-xs">{change.materialDescription}</td>
                                <td className="px-4 py-2 text-xs">{change.partType}</td>
                                <td className="num px-4 py-2">{change.unit}</td>
                                {NUMERIC_COMPARE_COLUMNS.map((column) => (
                                  <td
                                    key={column.key}
                                    className={`num px-4 py-2 text-right font-semibold ${deltaTone(change.numericDeltas[column.key])}`}
                                  >
                                    {formatDelta(change.numericDeltas[column.key])}
                                  </td>
                                ))}
                                <td className="px-4 py-2 text-center">
                                  <StatusBadge
                                    tone={
                                      change.change === "Added"
                                        ? "ok"
                                        : change.change === "Removed"
                                        ? "danger"
                                        : change.change === "Changed"
                                        ? "warn"
                                        : "neutral"
                                    }
                                  >
                                    {change.change}
                                  </StatusBadge>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  <div className="space-y-3 rounded-md border border-border bg-muted/20 p-3 lg:order-1">
                    <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
                      <History className="size-4 text-muted-foreground" />
                      Comparison instances
                    </div>
                    <div className="space-y-3 text-xs">
                      <div className="grid gap-1.5">
                        <label className="label-caps">First instance</label>
                        <Select
                          value={firstVersionId || String(compareResult.firstVersion.id)}
                          onValueChange={setFirstVersionId}
                        >
                          <SelectTrigger className="h-8 bg-background text-xs">
                            <SelectValue placeholder="Select BOM version" />
                          </SelectTrigger>
                          <SelectContent>
                            {compareVersions.map((version) => (
                              <SelectItem key={version.id} value={String(version.id)}>
                                v{version.version} — {version.source_filename}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <p className="text-muted-foreground">
                          {compareResult.firstLineCount} line{compareResult.firstLineCount === 1 ? "" : "s"} for {compareResult.fgpn}
                        </p>
                      </div>

                      <div className="grid gap-1.5 border-t border-border pt-3">
                        <label className="label-caps">Second instance</label>
                        <Select
                          value={secondVersionId || String(compareResult.secondVersion.id)}
                          onValueChange={setSecondVersionId}
                        >
                          <SelectTrigger className="h-8 bg-background text-xs">
                            <SelectValue placeholder="Select BOM version" />
                          </SelectTrigger>
                          <SelectContent>
                            {compareVersions.map((version) => (
                              <SelectItem key={version.id} value={String(version.id)}>
                                v{version.version} — {version.source_filename}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <p className="text-muted-foreground">
                          {compareResult.secondLineCount} line{compareResult.secondLineCount === 1 ? "" : "s"} for {compareResult.fgpn}
                        </p>
                      </div>

                      <div className="rounded-md border border-border bg-background p-2 text-[11px] text-muted-foreground">
                        Delta is calculated as second instance minus first instance for every numeric BOM column.
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </Section>
        </div>
      </div>

      {/* ── Full-screen overlay ── */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 flex flex-col bg-background p-4 sm:p-6">
          {/* Header */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-4 mb-0 shrink-0">
            <div className="flex items-center gap-3">
              <h2 className="text-base font-bold text-foreground">FGPN BOM Coverage</h2>
              <span className="text-xs text-muted-foreground">
                {fgpnRows.length} parts · {selectedPoNumbers.size} PO{selectedPoNumbers.size === 1 ? "" : "s"} selected
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
                <Input
                  value={fgpnFilter}
                  onChange={(e) => setFgpnFilter(e.target.value)}
                  placeholder="Filter FGPN or PO…"
                  className="h-8 w-64 pl-8 text-xs bg-background"
                  autoFocus
                />
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 gap-1.5 text-xs"
                onClick={() => setIsFullscreen(false)}
              >
                <Minimize2 className="size-3.5" />
                Exit full screen
              </Button>
            </div>
          </div>

          {/* Table */}
          <div className="flex-1 overflow-auto rounded-lg border border-border bg-card custom-scrollbar min-h-0">
            <table className="w-full min-w-[720px] text-sm">
              <CoverageHeader />
              <tbody>
                <CoverageRows rows={paginatedRows} colSpan={6} />
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <PaginationBar />
        </div>
      )}
    </>
  );
}
