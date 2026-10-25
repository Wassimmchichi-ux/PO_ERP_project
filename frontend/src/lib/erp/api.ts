import { toBackendRole } from "./backendRoles";
import { users } from "./data";

export const API_BASE_URL =
  (import.meta.env["VITE_API_BASE_URL"] as string | undefined) ?? "http://localhost:8000";

const SESSION_STORAGE_KEY = "erp.session.userId";

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(apiUrl(path), {
    ...init,
    headers: apiHeaders(init.headers),
  });
}

export function apiHeaders(headers?: HeadersInit): Headers {
  const next = new Headers(headers);
  const user = getActivePrototypeUser();
  if (user) next.set("X-ERP-Role", toBackendRole(user.role));
  return next;
}

export async function throwApiError(response: Response): Promise<never> {
  const payload = await response.json().catch(() => null);
  const detail = payload?.detail;

  if (typeof detail === "string") throw new Error(detail);
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => item?.msg ?? item?.message ?? String(item))
      .filter(Boolean);
    if (messages.length > 0) throw new Error(messages.join("; "));
  }
  if (typeof payload?.message === "string") throw new Error(payload.message);

  throw new Error(response.statusText || `Request failed with ${response.status}`);
}

export function readApiError(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === "object" && error !== null) {
    if ("message" in error) return String((error as { message: unknown }).message);
    if ("detail" in error) return String((error as { detail: unknown }).detail);
  }
  return fallback;
}

function getActivePrototypeUser() {
  if (typeof window === "undefined") return users.find((user) => user.id === "U03") ?? users[0];
  const stored = window.localStorage.getItem(SESSION_STORAGE_KEY);
  return (
    users.find((user) => user.id === stored) ?? users.find((user) => user.id === "U03") ?? users[0]
  );
}
