import { useMemo, useState, type ReactNode } from "react";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { EmptyState } from "./EmptyState";
import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  header: string;
  align?: "left" | "right" | "center";
  width?: string;
  mono?: boolean;
  cell: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number;
}

interface DataTableProps<T> {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string;
  searchable?: (row: T) => string;
  searchPlaceholder?: string;
  toolbar?: ReactNode;
  pageSize?: number;
  onRowClick?: (row: T) => void;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  rowTone?: (row: T) => "danger" | "warn" | undefined;
  dense?: boolean;
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  searchable,
  searchPlaceholder = "Search…",
  toolbar,
  pageSize = 12,
  onRowClick,
  emptyTitle = "No records",
  emptyDescription,
  emptyAction,
  rowTone,
  dense = true,
}: DataTableProps<T>) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);

  const filtered = useMemo(() => {
    let out = rows;
    if (searchable && query.trim().length > 0) {
      const q = query.trim().toLowerCase();
      out = out.filter((r) => searchable(r).toLowerCase().includes(q));
    }
    if (sort) {
      const col = columns.find((c) => c.key === sort.key);
      if (col?.sortValue) {
        out = [...out].sort((a, b) => {
          const av = col.sortValue!(a);
          const bv = col.sortValue!(b);
          if (av === bv) return 0;
          return (av > bv ? 1 : -1) * sort.dir;
        });
      }
    }
    return out;
  }, [rows, query, searchable, sort, columns]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const current = Math.min(page, pageCount - 1);
  const visible = filtered.slice(current * pageSize, current * pageSize + pageSize);

  return (
    <div>
      {(searchable || toolbar) && (
        <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2">
          {searchable && (
            <div className="relative min-w-[220px] flex-1 md:max-w-xs">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setPage(0);
                }}
                placeholder={searchPlaceholder}
                className="h-8 pl-8 text-xs"
              />
            </div>
          )}
          {toolbar}
        </div>
      )}

      {visible.length === 0 ? (
        <EmptyState
          title={query ? "No matching records" : emptyTitle}
          {...(query
            ? { description: `Nothing matches “${query}”. Adjust the search or filters.` }
            : emptyDescription
              ? { description: emptyDescription }
              : {})}
          {...(emptyAction && !query ? { action: emptyAction } : {})}
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/60">
                {columns.map((c) => (
                  <th
                    key={c.key}
                    style={c.width ? { width: c.width } : undefined}
                    className={cn(
                      "label-caps px-3 py-2 text-left font-semibold",
                      c.align === "right" && "text-right",
                      c.align === "center" && "text-center",
                      c.sortValue && "cursor-pointer select-none hover:text-foreground",
                    )}
                    onClick={
                      c.sortValue
                        ? () =>
                            setSort((s) =>
                              s?.key === c.key
                                ? { key: c.key, dir: s.dir === 1 ? -1 : 1 }
                                : { key: c.key, dir: 1 },
                            )
                        : undefined
                    }
                  >
                    {c.header}
                    {sort?.key === c.key && (sort.dir === 1 ? " ▲" : " ▼")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => {
                const tone = rowTone?.(row);
                return (
                  <tr
                    key={rowKey(row)}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    className={cn(
                      "border-b border-border last:border-0",
                      onRowClick && "cursor-pointer",
                      "hover:bg-muted/50",
                      tone === "danger" && "bg-danger-soft/50",
                      tone === "warn" && "bg-warn-soft/50",
                    )}
                  >
                    {columns.map((c) => (
                      <td
                        key={c.key}
                        className={cn(
                          "px-3 align-middle",
                          dense ? "py-1.5" : "py-2.5",
                          c.align === "right" && "text-right",
                          c.align === "center" && "text-center",
                          c.mono && "num",
                        )}
                      >
                        {c.cell(row)}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {filtered.length > pageSize && (
        <div className="flex items-center justify-between border-t border-border px-3 py-2 text-xs text-muted-foreground">
          <span>
            {current * pageSize + 1}–{Math.min(filtered.length, (current + 1) * pageSize)} of{" "}
            {filtered.length}
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2"
              disabled={current === 0}
              onClick={() => setPage(current - 1)}
            >
              <ChevronLeft className="size-3.5" />
            </Button>
            <span className="px-1">
              Page {current + 1} / {pageCount}
            </span>
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2"
              disabled={current >= pageCount - 1}
              onClick={() => setPage(current + 1)}
            >
              <ChevronRight className="size-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
