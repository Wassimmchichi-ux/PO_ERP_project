import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { PageHeader, Section } from "@/components/erp/PageHeader";
import { StatusBadge } from "@/components/erp/StatusBadge";
import { AccessDenied, EmptyState } from "@/components/erp/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useSession } from "@/lib/erp/session";
import { referenceEntries } from "@/lib/erp/data";
import type { ReferenceEntry, ReferenceListId } from "@/lib/erp/types";
import { pageTitle } from "@/lib/erp/appInfo";
import { apiFetch, readApiError, throwApiError } from "@/lib/erp/api";

export const Route = createFileRoute("/admin/reference-lists")({
  head: () => ({
    meta: [
      { title: pageTitle("Reference Lists") },
      {
        name: "description",
        content:
          "Maintain the controlled vocabularies used across the system: suppliers, JIT customers, contact names, finished goods part numbers, receivers, delivery methods and material types.",
      },
      { property: "og:title", content: pageTitle("Reference Lists") },
      {
        property: "og:description",
        content: "Values in use cannot be deleted, only deactivated, to protect existing records.",
      },
    ],
  }),
  component: ReferenceListsPage,
});

const LISTS: ReferenceListId[] = [
  "JIT Customers",
  "Contact Names",
  "Finished Goods Part Numbers",
  "Manufacturing Receivers",
  "Delivery Methods",
  "Material Types",
  "Suppliers",
];

function ReferenceListsPage() {
  const { can } = useSession();
  const [list, setList] = useState<ReferenceListId>("JIT Customers");
  const [value, setValue] = useState("");
  const [detail, setDetail] = useState("");
  const [items, setItems] = useState<ReferenceEntry[]>(referenceEntries);

  useEffect(() => {
    void fetchReferenceItems((loaded) => setItems(loaded));
  }, []);

  if (!can("admin.reference")) return <AccessDenied what="reference list administration" />;

  const entries = items.filter((e) => e.list === list);

  return (
    <>
      <PageHeader
        title="Reference lists"
        subtitle="Reference values feed the dropdowns used in purchase order intake, deliveries and stock screens."
        crumbs={[{ label: "Administration" }, { label: "Reference lists" }]}
      />

      <div className="grid gap-4 p-4 xl:grid-cols-[280px_minmax(0,1fr)]">
        <Section title="Lists">
          <ul className="divide-y divide-border">
            {LISTS.map((l) => {
              const count = items.filter((e) => e.list === l).length;
              return (
                <li key={l}>
                  <button
                    type="button"
                    onClick={() => setList(l)}
                    className={`flex w-full items-center justify-between px-4 py-2.5 text-left text-sm transition-colors hover:bg-muted/60 ${
                      list === l ? "bg-muted font-medium" : ""
                    }`}
                  >
                    {l}
                    <span className="num text-xs text-muted-foreground">{count}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </Section>

        <div className="space-y-4">
          <Section title={`Add a value to “${list}”`}>
            <div className="grid gap-3 p-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end">
              <div className="grid gap-1.5">
                <Label className="text-xs">
                  {list === "Suppliers" ? "Full legal supplier name" : "Value"}
                </Label>
                <Input
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  className="h-8 text-xs"
                  placeholder={list === "Suppliers" ? "Supplier full name" : "New reference value"}
                />
              </div>
              <div className="grid gap-1.5">
                <Label className="text-xs">
                  {list === "Suppliers" ? "Supplier reference" : "Detail (optional)"}
                </Label>
                <Input
                  value={detail}
                  onChange={(e) => setDetail(e.target.value)}
                  className="h-8 text-xs"
                  placeholder={
                    list === "Suppliers" ? "Required unique reference" : "Site, description or code"
                  }
                />
              </div>
              <Button
                className="h-8"
                disabled={!value.trim() || (list === "Suppliers" && !detail.trim())}
                onClick={() => {
                  void createReferenceItem(list, value, detail, (created) => {
                    setItems((current) => [...current, created]);
                    setValue("");
                    setDetail("");
                  });
                }}
              >
                <Plus className="size-3.5" /> Add value
              </Button>
            </div>
          </Section>

          <Section
            title={list}
            description="A value linked to existing records can be deactivated but never removed."
          >
            {entries.length === 0 ? (
              <EmptyState title="This list is empty" />
            ) : (
              <div className="max-h-[420px] overflow-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 z-10">
                    <tr className="border-b border-border bg-muted/95">
                      <th className="label-caps px-4 py-2 text-left">Value</th>
                      <th className="label-caps px-4 py-2 text-left">Detail</th>
                      <th className="label-caps px-4 py-2 text-right">Linked records</th>
                      <th className="label-caps px-4 py-2 text-left">State</th>
                      <th className="label-caps px-4 py-2 text-right">Active</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entries.map((e) => (
                      <tr key={e.id} className="border-b border-border last:border-0">
                        <td className="px-4 py-1.5 font-medium">{e.value}</td>
                        <td className="px-4 py-1.5 text-xs text-muted-foreground">
                          {e.detail ?? "—"}
                        </td>
                        <td className="num px-4 py-1.5 text-right">{e.linkedRecords}</td>
                        <td className="px-4 py-1.5">
                          {e.linkedRecords > 0 ? (
                            <StatusBadge tone="info">In use — cannot be deleted</StatusBadge>
                          ) : (
                            <StatusBadge tone="neutral">Not used yet</StatusBadge>
                          )}
                        </td>
                        <td className="px-4 py-1.5 text-right">
                          <Switch
                            checked={e.active}
                            onCheckedChange={(v) =>
                              void updateReferenceItem(e, { active: v }, (updated) =>
                                setItems((current) =>
                                  current.map((item) => (item.id === updated.id ? updated : item)),
                                ),
                              )
                            }
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>
        </div>
      </div>
    </>
  );
}

async function fetchReferenceItems(onLoaded: (items: ReferenceEntry[]) => void) {
  try {
    const response = await apiFetch("/admin/reference-lists");
    if (!response.ok) await throwApiError(response);
    const payload = (await response.json()) as { items: ApiReferenceItem[] };
    onLoaded(payload.items.map(mapApiReferenceItem));
  } catch {
    // Static seed values remain available for frontend-only demos.
  }
}

async function createReferenceItem(
  list: ReferenceListId,
  value: string,
  detail: string,
  onCreated: (item: ReferenceEntry) => void,
) {
  const trimmedValue = value.trim();
  const trimmedDetail = detail.trim();
  try {
    const response = await apiFetch(`/admin/reference-lists/${toReferenceSlug(list)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        value: trimmedValue,
        detail: trimmedDetail || null,
        code: list === "JIT Customers" ? undefined : list === "Suppliers" ? trimmedDetail : null,
        unit: list === "Material Types" ? trimmedDetail || "pcs" : null,
      }),
    });
    if (!response.ok) await throwApiError(response);
    const created = mapApiReferenceItem(await response.json());
    onCreated(created);
    toast.success(`“${created.value}” added to ${list}.`);
  } catch (error) {
    toast.error(readApiError(error, `Could not add “${trimmedValue}” in the backend.`));
  }
}

async function updateReferenceItem(
  item: ReferenceEntry,
  payload: { active: boolean },
  onUpdated: (item: ReferenceEntry) => void,
) {
  const local = { ...item, active: payload.active };
  if (item.id.startsWith("LOCAL-") || item.id.startsWith("RF-")) {
    toast.error("Connect the backend before changing seed reference data.");
    return;
  }
  try {
    const response = await apiFetch(
      `/admin/reference-lists/${toReferenceSlug(item.list)}/${referenceNumericId(item.id)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    if (!response.ok) await throwApiError(response);
    const updated = mapApiReferenceItem(await response.json());
    onUpdated(updated);
    toast.success(`“${updated.value}” ${updated.active ? "activated" : "deactivated"}.`);
  } catch (error) {
    toast.error(readApiError(error, "Could not update the reference value."));
  }
}

function mapApiReferenceItem(raw: ApiReferenceItem): ReferenceEntry {
  return {
    id: raw.id,
    list: raw.list as ReferenceListId,
    value: raw.value,
    ...(raw.detail == null ? {} : { detail: raw.detail }),
    active: raw.active,
    linkedRecords: raw.linked_records,
  };
}

function toReferenceSlug(list: ReferenceListId) {
  const map: Record<ReferenceListId, string> = {
    "JIT Customers": "customers",
    "ORM Customers": "customers",
    "Contact Names": "contacts",
    "Finished Goods Part Numbers": "finished-goods-part-numbers",
    "Manufacturing Receivers": "manufacturing-receivers",
    "Delivery Methods": "delivery-methods",
    "Material Types": "material-types",
    Suppliers: "suppliers",
  };
  return map[list];
}

function referenceNumericId(id: string) {
  return Number(id.split(":").at(1) ?? id);
}

interface ApiReferenceItem {
  id: string;
  list: string;
  value: string;
  detail: string | null;
  active: boolean;
  linked_records: number;
}
