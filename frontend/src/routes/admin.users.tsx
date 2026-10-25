import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { KeyRound, Lock, LockOpen, UserPlus } from "lucide-react";
import { PageHeader, Section } from "@/components/erp/PageHeader";
import { DataTable, type Column } from "@/components/erp/DataTable";
import { StatusBadge } from "@/components/erp/StatusBadge";
import { AccessDenied } from "@/components/erp/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSession } from "@/lib/erp/session";
import { projects, roles, users } from "@/lib/erp/data";
import { fmtDateTime } from "@/lib/erp/format";
import type { RoleId, User } from "@/lib/erp/types";
import { pageTitle } from "@/lib/erp/appInfo";
import { apiFetch, readApiError, throwApiError } from "@/lib/erp/api";
import { toBackendRole, toRoleId } from "@/lib/erp/backendRoles";

export const Route = createFileRoute("/admin/users")({
  head: () => ({
    meta: [
      { title: pageTitle("Users & Access") },
      {
        name: "description",
        content:
          "Administer user accounts, role assignment, project responsibility and account locking for the launch, warehouse and finance teams.",
      },
      { property: "og:title", content: pageTitle("Users & Access") },
      {
        property: "og:description",
        content: "Role-based access control for every module of the ERP prototype.",
      },
    ],
  }),
  component: AdminUsersPage,
});

function AdminUsersPage() {
  const { can } = useSession();
  const [roleFilter, setRoleFilter] = useState("all");
  const [managedUsers, setManagedUsers] = useState<User[]>(users);
  const [adminProjects, setAdminProjects] = useState<AdminProject[]>(
    projects.map((project) => ({ id: project.id, code: project.code, name: project.name })),
  );
  const [createForm, setCreateForm] = useState({
    fullName: "",
    registrationNumber: "",
    role: "R03" as RoleId,
  });

  useEffect(() => {
    void fetchAdminUsers((items) => setManagedUsers(items));
    void fetchAdminProjects((items) => setAdminProjects(items));
  }, []);

  if (!can("admin.users")) return <AccessDenied what="user administration" />;

  const rows = managedUsers.filter((u) => roleFilter === "all" || u.role === roleFilter);
  const roleName = (id: string) => roles.find((r) => r.id === id)?.name ?? id;
  const updateUser = (updated: User) =>
    setManagedUsers((current) => current.map((user) => (user.id === updated.id ? updated : user)));

  const columns: Column<User>[] = [
    {
      key: "name",
      header: "User",
      cell: (u) => (
        <span>
          <span className="font-medium">{u.fullName}</span>
          <span className="num ml-2 text-xs text-muted-foreground">{u.username}</span>
        </span>
      ),
      sortValue: (u) => u.fullName,
    },
    {
      key: "role",
      header: "Role",
      cell: (u) => (
        <Select
          value={u.role}
          onValueChange={(value) =>
            void patchUser(
              u,
              { role: toBackendRole(value as RoleId) },
              (updated) => updateUser(updated),
              `${u.username} role changed to ${roleName(value)}.`,
            )
          }
        >
          <SelectTrigger className="h-7 w-52 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {roles.map((role) => (
              <SelectItem key={role.id} value={role.id}>
                {role.id} — {role.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ),
      sortValue: (u) => u.role,
    },
    {
      key: "projects",
      header: "Project responsibility",
      cell: (u) => (
        <div className="grid min-w-64 gap-1.5">
          <div className="flex flex-wrap gap-1">
            {u.projectIds.length === 0 ? (
              <span className="text-xs text-muted-foreground">No owned project assignment</span>
            ) : (
              u.projectIds.map((pid) => (
                <StatusBadge key={pid} tone="neutral" dot={false}>
                  {adminProjects.find((p) => p.id === pid)?.code ?? `Project ${pid}`}
                </StatusBadge>
              ))
            )}
          </div>
          {(u.role === "R02" || u.role === "R03") && (
            <Select
              value=""
              onValueChange={(projectId) =>
                void assignProject(u, projectId, (updated) => updateUser(updated))
              }
            >
              <SelectTrigger className="h-7 w-48 text-xs">
                <SelectValue placeholder="Assign project" />
              </SelectTrigger>
              <SelectContent>
                {adminProjects.map((project) => (
                  <SelectItem
                    key={project.id}
                    value={project.id}
                    disabled={u.projectIds.includes(project.id)}
                  >
                    {project.code} — {project.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      ),
    },
    {
      key: "last",
      header: "Last login",
      mono: true,
      cell: (u) => fmtDateTime(u.lastLogin),
      sortValue: (u) => u.lastLogin ?? "",
    },
    {
      key: "state",
      header: "Account",
      cell: (u) => (
        <div className="flex items-center gap-2">
          <StatusBadge tone={u.active ? "ok" : "neutral"}>
            {u.active ? "Active" : "Deactivated"}
          </StatusBadge>
          {u.locked && <StatusBadge tone="danger">Locked</StatusBadge>}
        </div>
      ),
      sortValue: (u) => (u.active ? 0 : 1),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      cell: (u) => (
        <div className="flex items-center justify-end gap-2">
          <Button
            size="sm"
            variant="outline"
            className="h-7 px-2 text-xs"
            onClick={() =>
              void runUserCommand(u, "force-password-reset", (updated) => updateUser(updated))
            }
          >
            <KeyRound className="size-3.5" /> Reset password
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 px-2 text-xs"
            onClick={() =>
              void runUserCommand(u, u.locked ? "unlock" : "lock", (updated) => updateUser(updated))
            }
          >
            {u.locked ? <LockOpen className="size-3.5" /> : <Lock className="size-3.5" />}
            {u.locked ? "Unlock" : "Lock"}
          </Button>
          <Switch
            checked={u.active}
            onCheckedChange={(v) =>
              void runUserCommand(u, v ? "activate" : "deactivate", (updated) =>
                updateUser(updated),
              )
            }
          />
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Users & access"
        subtitle="Accounts are never deleted; deactivation preserves the audit trail of past actions."
        crumbs={[{ label: "Administration" }, { label: "Users & access" }]}
        meta={
          <>
            <StatusBadge tone="ok">
              {managedUsers.filter((u) => u.active).length} active
            </StatusBadge>
            <StatusBadge tone="danger">
              {managedUsers.filter((u) => u.locked).length} locked
            </StatusBadge>
          </>
        }
      />

      <div className="space-y-4 p-4">
        <Section title="Create administrator-managed account">
          <div className="grid gap-3 p-4 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_220px_auto] md:items-end">
            <div className="grid gap-1.5">
              <Label className="text-xs">Full name</Label>
              <Input
                value={createForm.fullName}
                onChange={(event) =>
                  setCreateForm((form) => ({ ...form, fullName: event.target.value }))
                }
                className="h-8 text-xs"
                placeholder="New user name"
              />
            </div>
            <div className="grid gap-1.5">
              <Label className="text-xs">Registration number</Label>
              <Input
                value={createForm.registrationNumber}
                onChange={(event) =>
                  setCreateForm((form) => ({ ...form, registrationNumber: event.target.value }))
                }
                className="h-8 text-xs"
                placeholder="u.registration"
              />
            </div>
            <div className="grid gap-1.5">
              <Label className="text-xs">Role</Label>
              <Select
                value={createForm.role}
                onValueChange={(value) =>
                  setCreateForm((form) => ({ ...form, role: value as RoleId }))
                }
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {roles.map((role) => (
                    <SelectItem key={role.id} value={role.id}>
                      {role.id} — {role.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              className="h-8"
              disabled={!createForm.fullName.trim() || !createForm.registrationNumber.trim()}
              onClick={() =>
                void createAdminUser(createForm, (created) => {
                  setManagedUsers((current) => [...current, created]);
                  setCreateForm({ fullName: "", registrationNumber: "", role: "R03" });
                })
              }
            >
              <UserPlus className="size-3.5" /> Create account
            </Button>
          </div>
        </Section>

        <Section
          title="User accounts"
          actions={
            <Select value={roleFilter} onValueChange={setRoleFilter}>
              <SelectTrigger className="h-8 w-64 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All roles</SelectItem>
                {roles.map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {r.id} — {r.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          }
        >
          <DataTable
            rows={rows}
            columns={columns}
            rowKey={(u) => u.id}
            searchable={(u) => `${u.fullName} ${u.username} ${roleName(u.role)}`}
            searchPlaceholder="Search name, username or role…"
            rowTone={(u) => (u.locked ? "danger" : !u.active ? "warn" : undefined)}
            emptyTitle="No user matches"
          />
        </Section>

        <Section
          title="Roles defined in the system"
          description="Role definitions are fixed by the specification; only the assignment of users to roles is administered here."
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/60">
                <th className="label-caps px-4 py-2 text-left">Code</th>
                <th className="label-caps px-4 py-2 text-left">Role</th>
                <th className="label-caps px-4 py-2 text-left">Short name</th>
                <th className="label-caps px-4 py-2 text-right">Users</th>
              </tr>
            </thead>
            <tbody>
              {roles.map((r) => (
                <tr key={r.id} className="border-b border-border last:border-0">
                  <td className="num px-4 py-1.5">{r.id}</td>
                  <td className="px-4 py-1.5 font-medium">{r.name}</td>
                  <td className="px-4 py-1.5 text-xs text-muted-foreground">{r.code}</td>
                  <td className="num px-4 py-1.5 text-right">
                    {managedUsers.filter((u) => u.role === r.id).length}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      </div>
    </>
  );
}

async function fetchAdminUsers(onLoaded: (items: User[]) => void) {
  try {
    const response = await apiFetch("/admin/users");
    if (!response.ok) await throwApiError(response);
    const payload = (await response.json()) as { items: ApiAdminUser[] };
    onLoaded(payload.items.map(mapApiUser));
  } catch {
    // Static seed users remain available for frontend-only demos.
  }
}

async function fetchAdminProjects(onLoaded: (items: AdminProject[]) => void) {
  try {
    const response = await apiFetch("/projects");
    if (!response.ok) await throwApiError(response);
    const payload = (await response.json()) as { items: ApiProject[] };
    onLoaded(
      payload.items.map((project) => ({
        id: String(project.project_id),
        code: project.project_code,
        name: project.name,
      })),
    );
  } catch {
    // Static project labels remain available for frontend-only demos.
  }
}

async function createAdminUser(
  form: { fullName: string; registrationNumber: string; role: RoleId },
  onCreated: (user: User) => void,
) {
  const fullName = form.fullName.trim();
  const registrationNumber = form.registrationNumber.trim();
  try {
    const response = await apiFetch("/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        full_name: fullName,
        registration_number: registrationNumber,
        role: toBackendRole(form.role),
      }),
    });
    if (!response.ok) await throwApiError(response);
    const created = mapApiUser(await response.json());
    onCreated(created);
    toast.success(`${created.username} created. Temporary password change is required.`);
  } catch (error) {
    toast.error(readApiError(error, "Could not create the account in the backend."));
  }
}

async function patchUser(
  user: User,
  payload: Partial<{
    role: string;
    status: string;
    must_change_password: boolean;
    project_ids: number[];
  }>,
  onUpdated: (user: User) => void,
  successMessage: string,
) {
  const local = {
    ...user,
    role: payload.role ? toRoleId(payload.role) : user.role,
    active: payload.status ? payload.status === "ACTIVE" : user.active,
    projectIds: payload.project_ids ? payload.project_ids.map(String) : user.projectIds,
  };
  if (user.id.startsWith("LOCAL-") || user.id.startsWith("U")) {
    toast.error("Connect the backend before saving changes to seed demo users.");
    return;
  }
  try {
    const response = await apiFetch(`/admin/users/${user.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) await throwApiError(response);
    onUpdated(mapApiUser(await response.json()));
    toast.success(successMessage);
  } catch (error) {
    toast.error(readApiError(error, "Could not update the account."));
  }
}

async function assignProject(user: User, projectId: string, onUpdated: (user: User) => void) {
  const nextIds = Array.from(new Set([...user.projectIds, projectId]));
  const projectIds = nextIds.map(Number);
  if (projectIds.some(Number.isNaN)) {
    toast.error("Connect the backend before assigning seed demo projects.");
    return;
  }
  await patchUser(
    user,
    { project_ids: projectIds },
    onUpdated,
    `Project ${projectId} assigned to ${user.username}.`,
  );
}

async function runUserCommand(
  user: User,
  command: "activate" | "deactivate" | "lock" | "unlock" | "force-password-reset",
  onUpdated: (user: User) => void,
) {
  const local: User = {
    ...user,
    active: command === "activate" ? true : command === "deactivate" ? false : user.active,
    ...(command === "lock"
      ? { locked: true }
      : command === "unlock"
        ? { locked: false }
        : user.locked === undefined
          ? {}
          : { locked: user.locked }),
  };
  const message =
    command === "force-password-reset"
      ? `Password reset required for ${user.username}.`
      : `${user.username} ${command.replace("deactivate", "deactivated").replace("activate", "activated").replace("unlock", "unlocked").replace("lock", "locked")}.`;
  if (user.id.startsWith("LOCAL-") || user.id.startsWith("U")) {
    toast.error("Connect the backend before saving changes to seed demo users.");
    return;
  }
  try {
    const response = await apiFetch(`/admin/users/${user.id}/${command}`, { method: "POST" });
    if (!response.ok) await throwApiError(response);
    onUpdated(mapApiUser(await response.json()));
    toast.success(message);
  } catch (error) {
    toast.error(readApiError(error, "Could not update the account."));
  }
}

function mapApiUser(raw: ApiAdminUser): User {
  return {
    id: raw.id,
    fullName: raw.full_name,
    username: raw.registration_number,
    role: toRoleId(raw.role),
    active: raw.status === "ACTIVE",
    locked: raw.is_locked,
    projectIds: raw.project_ids.map(String),
    ...(raw.last_login_at == null ? {} : { lastLogin: raw.last_login_at }),
  };
}

interface ApiAdminUser {
  id: string;
  full_name: string;
  registration_number: string;
  role: string;
  status: string;
  is_locked: boolean;
  must_change_password: boolean;
  failed_login_count: number;
  locked_at: string | null;
  last_login_at: string | null;
  created_at: string;
  project_ids: number[];
}

interface ApiProject {
  project_id: number;
  project_code: string;
  name: string;
}

interface AdminProject {
  id: string;
  code: string;
  name: string;
}
