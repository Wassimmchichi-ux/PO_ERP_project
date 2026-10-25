import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Crumb {
  label: string;
  to?: string;
}

export function PageHeader({
  title,
  subtitle,
  crumbs,
  meta,
  actions,
  className,
}: {
  title: string;
  subtitle?: string;
  crumbs?: Crumb[];
  meta?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("border-b border-border bg-card px-4 py-3", className)}>
      {crumbs && crumbs.length > 0 && (
        <nav
          aria-label="Breadcrumb"
          className="mb-1 flex items-center gap-1 text-xs text-muted-foreground"
        >
          {crumbs.map((crumb, idx) => {
            const isLast = idx === crumbs.length - 1;
            return (
              <span key={idx} className="flex items-center gap-1">
                {idx > 0 && <ChevronRight className="size-3 text-muted-foreground/60" />}
                {crumb.to && !isLast ? (
                  <Link to={crumb.to} className="hover:text-foreground">
                    {crumb.label}
                  </Link>
                ) : (
                  <span className={cn(isLast ? "font-medium text-foreground" : "")}>
                    {crumb.label}
                  </span>
                )}
              </span>
            );
          })}
        </nav>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-base font-semibold tracking-tight text-foreground">
            {title}
          </h1>
          {subtitle && <p className="truncate text-xs text-muted-foreground">{subtitle}</p>}
        </div>

        {(meta || actions) && (
          <div className="flex flex-wrap items-center gap-2">
            {meta && <div className="flex flex-wrap items-center gap-1.5">{meta}</div>}
            {actions && <div className="flex items-center gap-2">{actions}</div>}
          </div>
        )}
      </div>
    </div>
  );
}

export function Section({
  title,
  description,
  actions,
  className,
  children,
}: {
  title?: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <section className={cn("panel flex flex-col overflow-hidden custom-scrollbar", className)}>
      {(title || description || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5 shrink-0">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-foreground">{title}</h2>}
            {description && <p className="truncate text-xs text-muted-foreground">{description}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="flex-1 overflow-y-auto custom-scrollbar">{children}</div>
    </section>
  );
}

export interface KeyValueItem {
  label: string;
  value: ReactNode;
}

export function KeyValue({
  items,
  columns = 3,
  className,
}: {
  items: KeyValueItem[];
  columns?: 2 | 3 | 4;
  className?: string;
}) {
  const colClass =
    columns === 2
      ? "sm:grid-cols-2"
      : columns === 4
        ? "sm:grid-cols-2 lg:grid-cols-4"
        : "sm:grid-cols-2 lg:grid-cols-3";

  return (
    <dl className={cn("grid gap-4 p-4", colClass, className)}>
      {items.map((item, idx) => (
        <div key={idx} className="space-y-0.5">
          <dt className="label-caps">{item.label}</dt>
          <dd className="text-sm font-medium text-foreground">{item.value ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}
