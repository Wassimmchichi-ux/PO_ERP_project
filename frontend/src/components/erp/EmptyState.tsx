import { Inbox, ShieldOff, AlertTriangle } from "lucide-react";
import type { ReactNode } from "react";
import { Skeleton } from "@/components/ui/skeleton";

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-3 flex size-10 items-center justify-center rounded-md border border-border bg-muted text-muted-foreground">
        {icon ?? <Inbox className="size-5" />}
      </div>
      <p className="text-sm font-semibold text-foreground">{title}</p>
      {description && <p className="mt-1 max-w-md text-xs text-muted-foreground">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function AccessDenied({ what }: { what: string }) {
  return (
    <div className="p-4">
      <div className="panel">
        <EmptyState
          icon={<ShieldOff className="size-5" />}
          title="Access denied"
          description={`Your role does not grant access to ${what}. Permissions are defined per role in the system; contact the System Administrator if this is unexpected.`}
        />
      </div>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <EmptyState
      icon={<AlertTriangle className="size-5 text-danger" />}
      title="Could not load this data"
      description={message}
    />
  );
}

export function TableLoading({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="divide-y divide-border">
      {Array.from({ length: rows }).map((_, r) => (
        <div
          key={r}
          className="grid gap-4 px-3 py-2.5"
          style={{ gridTemplateColumns: `repeat(${cols}, minmax(0,1fr))` }}
        >
          {Array.from({ length: cols }).map((__, c) => (
            <Skeleton key={c} className="h-3.5 w-full" />
          ))}
        </div>
      ))}
    </div>
  );
}
