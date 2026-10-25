import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { projects, resolveProjectId, users } from "./data";
import { can, canWriteProject, visibleProjectIds, type Capability } from "./rbac";
import type { RoleId, User } from "./types";

const STORAGE_KEY = "erp.session.userId";

interface SessionValue {
  user: User;
  role: RoleId;
  setUserId: (id: string) => void;
  can: (cap: Capability) => boolean;
  projectIds: string[];
  canWrite: (projectId?: string | number | null) => boolean;
  activeProjectId: string | null;
  setActiveProjectId: (id: string | null) => void;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [userId, setUserIdState] = useState("U03");
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && users.some((u) => u.id === stored)) setUserIdState(stored);
  }, []);

  const value = useMemo<SessionValue>(() => {
    const user = (users.find((u) => u.id === userId) ?? users[0]) as User;
    const ids = visibleProjectIds(
      user.role,
      user.projectIds,
      projects.map((p) => p.id),
    );
    return {
      user,
      role: user.role,
      setUserId: (id: string) => {
        setUserIdState(id);
        setActiveProjectId(null);
        window.localStorage.setItem(STORAGE_KEY, id);
      },
      can: (cap) => can(user.role, cap),
      projectIds: ids,
      canWrite: (projectId) => {
        const resolvedId = resolveProjectId(projectId) ?? String(projectId ?? "");
        return canWriteProject(user.role, user.projectIds, resolvedId);
      },
      activeProjectId: activeProjectId && ids.includes(activeProjectId) ? activeProjectId : null,
      setActiveProjectId,
    };
  }, [userId, activeProjectId]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}

/** Filter any project-scoped collection by visibility + active project selector. */
export function useProjectScope() {
  const { projectIds, activeProjectId } = useSession();
  return useMemo(
    () => ({
      ids: activeProjectId ? [activeProjectId] : projectIds,
      inScope: (projectId?: string | number | null) => {
        if (!projectId) return true;
        const resolvedId = resolveProjectId(projectId) ?? String(projectId);
        return activeProjectId ? resolvedId === activeProjectId : projectIds.includes(resolvedId);
      },
    }),
    [projectIds, activeProjectId],
  );
}
