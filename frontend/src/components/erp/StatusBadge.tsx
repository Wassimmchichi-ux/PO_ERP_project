import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badge = cva(
  "inline-flex items-center gap-1.5 whitespace-nowrap rounded-sm border px-1.5 py-0.5 text-[11px] font-semibold leading-4 tracking-tight",
  {
    variants: {
      tone: {
        neutral: "border-border bg-neutral-soft text-muted-foreground",
        info: "border-info/25 bg-info-soft text-info",
        ok: "border-ok/25 bg-ok-soft text-ok",
        warn: "border-warn/30 bg-warn-soft text-warn",
        danger: "border-danger/25 bg-danger-soft text-danger",
        accent: "border-accent/40 bg-accent/15 text-accent-foreground",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export type Tone = NonNullable<VariantProps<typeof badge>["tone"]>;

export function StatusBadge({
  children,
  tone = "neutral",
  dot = true,
  className = "",
}: {
  children: React.ReactNode;
  tone?: Tone;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span className={cn(badge({ tone }), className)}>
      {dot && <span className="size-1.5 rounded-full bg-current opacity-80" />}
      {children}
    </span>
  );
}

const MAP: Record<string, Tone> = {
  // PO lifecycle
  Unplanned: "neutral",
  "In Progress": "info",
  Done: "accent",
  Packaged: "warn",
  Delivered: "ok",
  // Field validation
  Validated: "ok",
  Mismatch: "danger",
  Missing: "warn",
  "Not Applicable": "neutral",
  // Feasibility
  "Fully feasible": "ok",
  "Partially feasible": "warn",
  "Not feasible": "danger",
  // Handover
  "Code issued": "info",
  "Code used": "info",
  "Document generated": "accent",
  "Awaiting validation": "warn",
  "Code expired": "danger",
  // Customer delivery
  Planned: "neutral",
  "Pending confirmation": "warn",
  // Generic
  Active: "ok",
  Inactive: "neutral",
  "On Hold": "warn",
  Closed: "neutral",
  Approved: "ok",
  Draft: "neutral",
  Locked: "neutral",
};

export function toneFor(value: string): Tone {
  return MAP[value] ?? "neutral";
}

export function AutoBadge({ value, className = "" }: { value: string; className?: string }) {
  return (
    <StatusBadge tone={toneFor(value)} className={className}>
      {value}
    </StatusBadge>
  );
}
