export const nf = new Intl.NumberFormat("en-GB", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

export const money = (v: number) =>
  new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(v);

export const qty = (v: number, unit?: string) => `${nf.format(v)}${unit ? ` ${unit}` : ""}`;

export function fmtDate(iso?: string) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function fmtDateTime(iso?: string) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })} ${d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`;
}

/** Fixed "now" so the prototype's countdowns and expiry states stay stable. */
export const NOW = new Date("2026-08-14T10:00:00");

export function hoursBetween(a: Date, b: Date) {
  return (b.getTime() - a.getTime()) / 3_600_000;
}

/** Remaining time in the 24 h warehouse correction window (M07-FR-05/06). */
export function correctionWindow(receivedAt: string) {
  const received = new Date(receivedAt);
  const elapsed = hoursBetween(received, NOW);
  const remaining = 24 - elapsed;
  if (remaining <= 0) return { locked: true as const, label: "Locked" };
  const h = Math.floor(remaining);
  const m = Math.floor((remaining - h) * 60);
  return { locked: false as const, label: `Locks in ${h}h ${m}m` };
}

/** Delivery code validity (M08-FR-05, 48 h). */
export function codeValidity(expiresAt: string, used: boolean) {
  if (used) return { state: "used" as const, label: "Already used" };
  const remaining = hoursBetween(NOW, new Date(expiresAt));
  if (remaining <= 0) return { state: "expired" as const, label: "Expired" };
  const h = Math.floor(remaining);
  const m = Math.floor((remaining - h) * 60);
  return { state: "valid" as const, label: `Valid ${h}h ${m}m` };
}

export function isoWeek(dateIso: string) {
  const d = new Date(dateIso);
  const target = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNum = (target.getUTCDay() + 6) % 7;
  target.setUTCDate(target.getUTCDate() - dayNum + 3);
  const firstThursday = new Date(Date.UTC(target.getUTCFullYear(), 0, 4));
  const diff = target.getTime() - firstThursday.getTime();
  return `W${1 + Math.round(diff / (7 * 86_400_000))}`;
}

export function periodLabel(period: string) {
  const [y, m] = period.split("-");
  return new Date(Number(y), Number(m) - 1, 1).toLocaleDateString("en-GB", {
    month: "short",
    year: "numeric",
  });
}
