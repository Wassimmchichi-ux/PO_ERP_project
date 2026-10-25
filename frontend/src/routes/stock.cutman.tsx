import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { PageHeader, Section } from "@/components/erp/PageHeader";
import { AccessDenied } from "@/components/erp/EmptyState";
import { FileDropzone } from "@/components/erp/FileDropzone";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSession } from "@/lib/erp/session";
import { nf, fmtDateTime } from "@/lib/erp/format";
import { pageTitle } from "@/lib/erp/appInfo";
import { apiFetch, readApiError, throwApiError } from "@/lib/erp/api";
import { stockHistoryQueryKey, stockSummaryQueryKey } from "@/lib/erp/stockApi";

export const Route = createFileRoute("/stock/cutman")({
  head: () => ({ meta: [{ title: pageTitle("Cutting Reports") }] }),
  component: CutManPage,
});

interface CuttingReport {
  report_id: number;
  file_name: string;
  imported_at: string;
  posted_at: string | null;
  posted_launch_id: number | null;
  confirmed_usage_unit: string | null;
  already_imported: boolean;
  warnings: string[];
  lines: {
    row_number: number;
    material_part_number: string;
    description: string;
    started_at: string;
    spreading_usage: string;
    raw_fields: Record<string, string>;
  }[];
}
const reportKey = ["stock", "cutting-reports"] as const;

async function readReports(): Promise<CuttingReport[]> {
  const response = await apiFetch("/stock/cutting-reports");
  if (!response.ok) await throwApiError(response);
  return response.json();
}

function CutManPage() {
  const { can } = useSession();
  const queryClient = useQueryClient();
  const reports = useQuery({
    queryKey: reportKey,
    queryFn: readReports,
    enabled: can("stock.monitor"),
  });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [launchId, setLaunchId] = useState("");
  const [unit, setUnit] = useState("m");
  const [confirmed, setConfirmed] = useState(false);
  const selected =
    reports.data?.find((report) => report.report_id === selectedId) ?? reports.data?.[0];
  const writable = can("stock.cutman.import");
  const upload = useMutation({
    mutationFn: async (file: File): Promise<CuttingReport> => {
      const body = new FormData();
      body.append("file", file);
      const response = await apiFetch("/stock/cutting-reports", { method: "POST", body });
      if (!response.ok) await throwApiError(response);
      return response.json();
    },
    onSuccess: (report) => {
      setSelectedId(report.report_id);
      setConfirmed(false);
      void queryClient.invalidateQueries({ queryKey: reportKey });
      toast.success(
        report.already_imported
          ? "This source file is already imported."
          : "Report imported for review. Stock has not changed.",
      );
    },
    onError: (error) => toast.error(readApiError(error, "Could not import the report.")),
  });
  const post = useMutation({
    mutationFn: async (): Promise<CuttingReport> => {
      if (!selected || !confirmed) throw new Error("Confirm the selected report before posting.");
      const response = await apiFetch(`/stock/cutting-reports/${selected.report_id}/post`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          launch_id: Number(launchId),
          usage_unit: unit,
          confirm_usage_is_consumption: true,
        }),
      });
      if (!response.ok) await throwApiError(response);
      return response.json();
    },
    onSuccess: () => {
      setConfirmed(false);
      void queryClient.invalidateQueries({ queryKey: reportKey });
      void queryClient.invalidateQueries({ queryKey: stockSummaryQueryKey });
      void queryClient.invalidateQueries({ queryKey: stockHistoryQueryKey });
      toast.success("Consumption posted. Remaining production stock has been updated.");
    },
    onError: (error) => toast.error(readApiError(error, "Could not post consumption.")),
  });
  const downloadSource = async () => {
    if (!selected) return;
    try {
      const response = await apiFetch(`/stock/cutting-reports/${selected.report_id}/source`);
      if (!response.ok) await throwApiError(response);
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = selected.file_name;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      toast.error(readApiError(error, "Could not download the source."));
    }
  };

  if (!can("stock.monitor")) return <AccessDenied what="cutting reports" />;
  return (
    <>
      <PageHeader
        title="Cutting reports"
        subtitle="Import source usage, review its meaning and launch, then confirm consumption."
        crumbs={[{ label: "Stock", to: "/stock" }, { label: "Cutting reports" }]}
      />
      <div className="grid gap-4 p-4 lg:grid-cols-[340px_minmax(0,1fr)]">
        <div className="space-y-4">
          {writable && (
            <Section title="Import a cutting report">
              <div className="space-y-3 p-4">
                <FileDropzone
                  accept={[".xlsx"]}
                  label={upload.isPending ? "Importing…" : "Choose the cutting report"}
                  hint="XLSX export with Start date, Start time, Material and Spreading Usage columns."
                  onFileAccepted={(file) => {
                    if (!upload.isPending) upload.mutate(file);
                  }}
                />
                <p className="text-xs text-muted-foreground">
                  Blank formatted rows are ignored. Import retains the original workbook and does
                  not change warehouse or production quantities.
                </p>
              </div>
            </Section>
          )}
          <Section title="Import history">
            <div className="space-y-2 p-4">
              <Button variant="outline" size="sm" onClick={() => void reports.refetch()}>
                Refresh
              </Button>
              {reports.isPending && <p role="status">Loading reports…</p>}
              {reports.isError && (
                <p className="text-sm text-danger" role="alert">
                  {readApiError(reports.error, "Could not load reports.")}
                </p>
              )}
              {reports.data?.map((report) => (
                <button
                  key={report.report_id}
                  className={`w-full rounded border p-3 text-left text-sm ${selected?.report_id === report.report_id ? "border-primary" : "border-border"}`}
                  onClick={() => {
                    setSelectedId(report.report_id);
                    setConfirmed(false);
                  }}
                >
                  <p className="font-medium">{report.file_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {fmtDateTime(report.imported_at)} · {report.lines.length} row(s) ·{" "}
                    {report.posted_at ? "Posted" : "Awaiting review"}
                  </p>
                </button>
              ))}
              {reports.isSuccess && reports.data.length === 0 && (
                <p className="text-sm text-muted-foreground">No cutting reports imported yet.</p>
              )}
            </div>
          </Section>
        </div>
        <div className="min-w-0 space-y-4">
          <Section title="Reported cutting usage">
            <div className="overflow-x-auto p-4">
              {selected ? (
                <>
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-medium">{selected.file_name}</p>
                    <Button variant="outline" size="sm" onClick={() => void downloadSource()}>
                      Download original
                    </Button>
                  </div>
                  {selected.warnings.map((warning) => (
                    <p key={warning} className="mb-2 text-xs text-muted-foreground">
                      {warning}
                    </p>
                  ))}
                  <table className="w-full min-w-[650px] text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="p-2 text-left">Material</th>
                        <th className="p-2 text-left">Started</th>
                        <th className="p-2 text-right">Spreading Usage</th>
                        <th className="p-2 text-right">CNC Length</th>
                        <th className="p-2 text-left">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selected.lines.map((line, index) => (
                        <tr key={`${line.row_number}-${index}`} className="border-b">
                          <td className="p-2">
                            {line.material_part_number}
                            <p className="text-xs text-muted-foreground">{line.description}</p>
                          </td>
                          <td className="p-2">{fmtDateTime(line.started_at)}</td>
                          <td className="p-2 text-right">
                            {nf.format(Number(line.spreading_usage))}
                          </td>
                          <td className="p-2 text-right">{line.raw_fields["CNC Length"] || "—"}</td>
                          <td className="p-2">
                            {line.raw_fields["Last status"] || "Not provided"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Import a report to inspect its source rows.
                </p>
              )}
            </div>
          </Section>
          {selected && !selected.posted_at && writable && (
            <Section title="Confirm consumption">
              <form
                className="space-y-4 p-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  post.mutate();
                }}
              >
                <p className="text-sm text-muted-foreground">
                  The report does not supply a launch or unit. Confirm them before treating
                  Spreading Usage as consumption. Materials must exist and have enough received
                  production stock.
                </p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="grid gap-1.5">
                    <Label htmlFor="cutting-launch">Launch ID</Label>
                    <Input
                      id="cutting-launch"
                      type="number"
                      min="1"
                      step="1"
                      required
                      value={launchId}
                      onChange={(event) => {
                        setLaunchId(event.target.value);
                        setConfirmed(false);
                      }}
                    />
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="cutting-unit">Confirmed usage unit</Label>
                    <select
                      id="cutting-unit"
                      className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                      value={unit}
                      onChange={(event) => {
                        setUnit(event.target.value);
                        setConfirmed(false);
                      }}
                    >
                      <option value="m">Metres (m)</option>
                      <option value="sqm">Square metres (sqm)</option>
                      <option value="pcs">Pieces (pcs)</option>
                      <option value="kg">Kilograms (kg)</option>
                    </select>
                  </div>
                </div>
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={confirmed}
                    onChange={(event) => setConfirmed(event.target.checked)}
                    className="mt-1"
                  />
                  I confirm that all rows represent new consumption for this launch in this unit,
                  not remaining-stock balances.
                </label>
                <Button
                  disabled={
                    post.isPending ||
                    !confirmed ||
                    !Number.isInteger(Number(launchId)) ||
                    Number(launchId) <= 0
                  }
                >
                  {post.isPending ? "Posting…" : "Post confirmed consumption"}
                </Button>
              </form>
            </Section>
          )}
          {selected?.posted_at && (
            <p className="text-sm">
              Posted {fmtDateTime(selected.posted_at)} · Launch #{selected.posted_launch_id} · Unit:{" "}
              {selected.confirmed_usage_unit}
            </p>
          )}
        </div>
      </div>
    </>
  );
}
