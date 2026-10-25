import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/erp/PageHeader";
import { DataTable, type Column } from "@/components/erp/DataTable";
import { AutoBadge } from "@/components/erp/StatusBadge";
import { AccessDenied } from "@/components/erp/EmptyState";
import { ConfirmDialog } from "@/components/erp/ConfirmDialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useProjectScope, useSession } from "@/lib/erp/session";
import { projects, purchaseOrders, users } from "@/lib/erp/data";
import { fmtDate } from "@/lib/erp/format";
import type { Project } from "@/lib/erp/types";
import { pageTitle } from "@/lib/erp/appInfo";
import { apiFetch, readApiError, throwApiError } from "@/lib/erp/api";

export const Route = createFileRoute("/projects/")({
  head: () => ({
    meta: [
      { title: pageTitle("Projects") },
      {
        name: "description",
        content:
          "Project register with assigned launch engineers, purchase order counts and current statuses. Access is limited to assigned projects.",
      },
      { property: "og:title", content: pageTitle("Projects") },
      {
        property: "og:description",
        content: "Top-level project grouping for purchase orders, stock and launch operations.",
      },
    ],
  }),
  component: ProjectsPage,
});

function ProjectsPage() {
  const { can, canWrite, user } = useSession();
  const scope = useProjectScope();
  const navigate = useNavigate();
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
  const [localProjects, setLocalProjects] = useState<Project[]>([]);
  const [hiddenProjectIds, setHiddenProjectIds] = useState<string[]>([]);
  const [createForm, setCreateForm] = useState({
    code: "",
    name: "",
    customer: "",
    carModel: "",
  });
  const [meetingDocumentId, setMeetingDocumentId] = useState("");
  const [deactivationReason, setDeactivationReason] = useState("");

  if (!can("project.view")) return <AccessDenied what="the project register" />;

  const rows = [
    ...localProjects,
    ...projects.filter((project) => !localProjects.some((local) => local.id === project.id)),
  ]
    .filter((p) => !hiddenProjectIds.includes(p.id))
    .filter((p) => localProjects.some((local) => local.id === p.id) || scope.inScope(p.id));

  const columns: Column<Project>[] = [
    {
      key: "code",
      header: "Project",
      cell: (p) => (
        <Link
          to="/projects/$projectId"
          params={{ projectId: p.id }}
          className="font-medium text-info hover:underline"
        >
          <span className="num">{p.code}</span> · {p.name}
        </Link>
      ),
      sortValue: (p) => p.code,
    },
    { key: "customer", header: "JIT customer", cell: (p) => p.customer },
    { key: "model", header: "Car model", cell: (p) => p.carModel ?? "—", mono: true },
    {
      key: "engineers",
      header: "Responsible users",
      cell: (p) =>
        p.responsibleUserIds
          .map((id) => users.find((u) => u.id === id)?.fullName ?? id)
          .join(", ") || "—",
    },
    {
      key: "pos",
      header: "POs",
      align: "right",
      mono: true,
      cell: (p) => purchaseOrders.filter((po) => po.projectId === p.id).length,
      sortValue: (p) => purchaseOrders.filter((po) => po.projectId === p.id).length,
    },
    {
      key: "open",
      header: "Open POs",
      align: "right",
      mono: true,
      cell: (p) =>
        purchaseOrders.filter((po) => po.projectId === p.id && po.status !== "Delivered").length,
    },
    { key: "created", header: "Created", cell: (p) => fmtDate(p.createdAt), mono: true },
    { key: "status", header: "Status", cell: (p) => <AutoBadge value={p.status} /> },
    {
      key: "actions",
      header: "",
      align: "right",
      cell: (p) =>
        canWrite(p.id) ? (
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-danger"
            onClick={(e) => {
              e.stopPropagation();
              setDeleteTarget(p);
            }}
          >
            <Trash2 className="size-3.5" />
          </Button>
        ) : null,
    },
  ];

  const linkedPos = deleteTarget
    ? purchaseOrders.filter((po) => po.projectId === deleteTarget.id).length
    : 0;

  return (
    <>
      <PageHeader
        title="Projects"
        subtitle="A project is the top-level grouping for purchase orders, BOMs, stock operations and deliveries."
        crumbs={[{ label: "Projects" }]}
        actions={
          can("project.write") ? (
            <Button size="sm" className="h-8" onClick={() => setCreateOpen(true)}>
              <Plus className="size-3.5" /> New project
            </Button>
          ) : null
        }
      />
      <div className="p-4">
        <div className="panel overflow-hidden">
          <DataTable
            rows={rows}
            columns={columns}
            rowKey={(p) => p.id}
            searchable={(p) => `${p.code} ${p.name} ${p.customer} ${p.carModel ?? ""}`}
            searchPlaceholder="Search project code, name or customer…"
            onRowClick={(p) =>
              void navigate({ to: "/projects/$projectId", params: { projectId: p.id } })
            }
            emptyTitle="No projects assigned to you"
            emptyDescription="Only projects assigned by the System Administrator are visible in your session."
          />
        </div>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create project</DialogTitle>
            <DialogDescription>
              A project must exist before any purchase order can be submitted against it.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="grid gap-1.5">
              <Label className="text-xs">Project code</Label>
              <Input
                value={createForm.code}
                onChange={(event) =>
                  setCreateForm((form) => ({ ...form, code: event.target.value }))
                }
                placeholder="P-2301"
                className="h-8"
              />
            </div>
            <div className="grid gap-1.5">
              <Label className="text-xs">Project name</Label>
              <Input
                value={createForm.name}
                onChange={(event) =>
                  setCreateForm((form) => ({ ...form, name: event.target.value }))
                }
                placeholder="Covers D-SUV Seat Trim"
                className="h-8"
              />
            </div>
            <div className="grid gap-1.5">
              <Label className="text-xs">JIT customer</Label>
              <Input
                value={createForm.customer}
                onChange={(event) =>
                  setCreateForm((form) => ({ ...form, customer: event.target.value }))
                }
                placeholder="Aurea Automotive"
                className="h-8"
              />
            </div>
            <div className="grid gap-1.5">
              <Label className="text-xs">Car model</Label>
              <Input
                value={createForm.carModel}
                onChange={(event) =>
                  setCreateForm((form) => ({ ...form, carModel: event.target.value }))
                }
                placeholder="D-SUV MY28"
                className="h-8"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!createForm.code.trim() || !createForm.name.trim()}
              onClick={() => {
                void createProjectFromForm(createForm, user.id, (project) => {
                  setLocalProjects((current) => [...current, project]);
                  setCreateForm({ code: "", name: "", customer: "", carModel: "" });
                  setCreateOpen(false);
                });
              }}
            >
              Create project
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(v) => !v && setDeleteTarget(null)}
        title={linkedPos > 0 ? "Deactivate project?" : "Delete project?"}
        destructive={linkedPos === 0}
        disabled={linkedPos > 0 && (!meetingDocumentId || !deactivationReason)}
        confirmLabel={linkedPos > 0 ? "Deactivate project" : "Delete project"}
        description={
          linkedPos > 0
            ? `${deleteTarget?.code} has ${linkedPos} linked purchase order(s). It will stay in history and become inactive once the meeting document is attached.`
            : `${deleteTarget?.code} will be removed. This action is irreversible and is recorded in the audit trail.`
        }
        onConfirm={() => {
          if (!deleteTarget) return;
          if (linkedPos > 0) {
            void deactivateProjectFromDialog(
              deleteTarget,
              Number(meetingDocumentId),
              deactivationReason,
              (project) => {
                setLocalProjects((current) => [
                  ...current.filter((item) => item.id !== project.id),
                  project,
                ]);
                setDeleteTarget(null);
                setMeetingDocumentId("");
                setDeactivationReason("");
              },
            );
            return;
          }
          void deleteProjectFromDialog(deleteTarget, () => {
            setHiddenProjectIds((current) => [...current, deleteTarget.id]);
            setDeleteTarget(null);
          });
        }}
      >
        {linkedPos > 0 && (
          <div className="grid gap-3">
            <div className="grid gap-1.5">
              <Label className="text-xs">Meeting document ID</Label>
              <Input
                value={meetingDocumentId}
                onChange={(event) => setMeetingDocumentId(event.target.value.replace(/\D/g, ""))}
                placeholder="Document ID for the deactivation meeting"
                className="h-8 text-xs"
              />
            </div>
            <div className="grid gap-1.5">
              <Label className="text-xs">Reason</Label>
              <Input
                value={deactivationReason}
                onChange={(event) => setDeactivationReason(event.target.value)}
                placeholder="Decision summary from the meeting"
                className="h-8 text-xs"
              />
            </div>
          </div>
        )}
      </ConfirmDialog>
    </>
  );
}

async function createProjectFromForm(
  form: { code: string; name: string; customer: string; carModel: string },
  ownerId: string,
  onCreated: (project: Project) => void,
) {
  try {
    const response = await apiFetch("/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_code: form.code.trim(),
        name: form.name.trim(),
        jit_customer: form.customer.trim() || null,
        car_model: form.carModel.trim() || null,
      }),
    });
    if (!response.ok) await throwApiError(response);
    const project = mapApiProject(await response.json());
    onCreated(project);
    toast.success(`${project.code} created and assigned to the project register.`);
  } catch (error) {
    toast.error(readApiError(error, "Could not create the project in the backend."));
  }
}

async function deleteProjectFromDialog(project: Project, onDeleted: () => void) {
  try {
    if (!project.id.startsWith("LOCAL-") && /^\d+$/.test(project.id)) {
      const response = await apiFetch(`/projects/${project.id}`, { method: "DELETE" });
      if (!response.ok) await throwApiError(response);
    } else {
      toast.error("Connect the backend before deleting seed demo projects.");
      return;
    }
    onDeleted();
    toast.success(`${project.code} deleted.`);
  } catch (error) {
    toast.error(readApiError(error, "Could not delete the project."));
  }
}

async function deactivateProjectFromDialog(
  project: Project,
  meetingDocumentId: number,
  reason: string,
  onDeactivated: (project: Project) => void,
) {
  try {
    if (!project.id.startsWith("LOCAL-") && /^\d+$/.test(project.id)) {
      const response = await apiFetch(`/projects/${project.id}/deactivate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ meeting_document_id: meetingDocumentId, reason }),
      });
      if (!response.ok) await throwApiError(response);
      onDeactivated(mapApiProject(await response.json()));
    } else {
      toast.error("Connect the backend before deactivating seed demo projects.");
      return;
    }
    toast.success(`${project.code} deactivated with meeting proof.`);
  } catch (error) {
    toast.error(readApiError(error, "Could not deactivate the project."));
  }
}

function mapApiProject(raw: ApiProject): Project {
  return {
    id: String(raw.project_id),
    code: raw.project_code,
    name: raw.name,
    customer: raw.jit_customer ?? "Not assigned",
    ...(raw.oem_customer == null ? {} : { oemCustomer: raw.oem_customer }),
    ...(raw.contact_name == null ? {} : { contactName: raw.contact_name }),
    ...(raw.contact_email == null ? {} : { contactEmail: raw.contact_email }),
    ...(raw.contact_phone == null ? {} : { contactPhone: raw.contact_phone }),
    ...(raw.car_model == null ? {} : { carModel: raw.car_model }),
    responsibleUserIds: raw.launch_engineer_user_id ? [raw.launch_engineer_user_id] : [],
    status: raw.status === "Inactive" ? "On Hold" : "Active",
    createdAt: raw.created_at,
  };
}

interface ApiProject {
  project_id: number;
  project_code: string;
  name: string;
  launch_engineer_user_id: string | null;
  status: string;
  jit_customer: string | null;
  oem_customer: string | null;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  car_model: string | null;
  created_at: string;
}
