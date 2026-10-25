import { useState, useMemo } from "react";
import {
  ChevronDown,
  ChevronRight,
  Folder,
  FolderOpen,
  Box,
  Search,
  Layers,
  CheckCheck,
  RotateCcw,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { purchaseOrders, findProject } from "@/lib/erp/data";
import { nf } from "@/lib/erp/format";
import type { PurchaseOrder, PoLine } from "@/lib/erp/types";

export interface SelectedFgpnItem {
  poId: string;
  poNumber: string;
  projectId: string;
  fgpn: string;
  description?: string;
  quantity: number;
  remainingQty: number;
}

interface SimulationPoTreeProps {
  projectId?: string;
  selectedFgpnKeys: Set<string>;
  onSelectionChange: (selectedKeys: Set<string>) => void;
}

export function SimulationPoTree({
  projectId,
  selectedFgpnKeys,
  onSelectionChange,
}: SimulationPoTreeProps) {
  const [search, setSearch] = useState("");
  const [expandedPos, setExpandedPos] = useState<Set<string>>(
    () => new Set(purchaseOrders.map((po) => po.id)),
  );

  // Filter POs according to active project scope if specified
  const filteredPOs = useMemo(() => {
    let list = purchaseOrders.filter((po) => po.status !== "Delivered");
    if (projectId && projectId !== "all") {
      list = list.filter((po) => po.projectId === projectId);
    }
    return list;
  }, [projectId]);

  // Tree items with search capability
  const treeData = useMemo(() => {
    const q = search.trim().toLowerCase();
    return filteredPOs
      .map((po) => {
        const remainingLines = po.lines.map((l) => ({
          ...l,
          remaining: Math.max(0, l.quantity - l.deliveredQuantity),
          key: `${po.id}::${l.id}`,
        }));

        if (!q) {
          return { po, lines: remainingLines };
        }

        const matchesPo =
          po.poNumber.toLowerCase().includes(q) ||
          po.jitCustomer.toLowerCase().includes(q) ||
          po.carModel?.toLowerCase().includes(q);

        const matchingLines = remainingLines.filter(
          (l) =>
            l.fgpn.toLowerCase().includes(q) ||
            (l.description && l.description.toLowerCase().includes(q)),
        );

        if (matchesPo) {
          return { po, lines: remainingLines };
        }
        if (matchingLines.length > 0) {
          return { po, lines: matchingLines };
        }
        return null;
      })
      .filter(Boolean) as {
      po: PurchaseOrder;
      lines: (PoLine & { remaining: number; key: string })[];
    }[];
  }, [filteredPOs, search]);

  const toggleExpand = (poId: string) => {
    setExpandedPos((prev) => {
      const next = new Set(prev);
      if (next.has(poId)) next.delete(poId);
      else next.add(poId);
      return next;
    });
  };

  const handleSelectPo = (
    po: PurchaseOrder,
    lines: { key: string }[],
    currentCheckState: boolean,
  ) => {
    const next = new Set(selectedFgpnKeys);
    if (currentCheckState) {
      lines.forEach((l) => next.delete(l.key));
    } else {
      lines.forEach((l) => next.add(l.key));
    }
    onSelectionChange(next);
  };

  const handleToggleFgpn = (key: string) => {
    const next = new Set(selectedFgpnKeys);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    onSelectionChange(next);
  };

  const handleSelectAll = () => {
    const allKeys = new Set<string>();
    treeData.forEach((item) => {
      item.lines.forEach((l) => allKeys.add(l.key));
    });
    onSelectionChange(allKeys);
  };

  const handleClearAll = () => {
    onSelectionChange(new Set());
  };

  return (
    <div className="flex h-full flex-col border-r border-border bg-card">
      {/* Header */}
      <div className="space-y-2 border-b border-border p-3 shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Layers className="size-4 text-accent" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">
              PO & FGPN Tree
            </h3>
          </div>
          <Badge variant="secondary" className="h-5 px-1.5 font-mono text-[10px]">
            {selectedFgpnKeys.size} selected
          </Badge>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-2 size-3.5 text-muted-foreground" />
          <Input
            placeholder="Search PO, FGPN, customer..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-7 pl-8 text-xs bg-muted/30"
          />
        </div>

        {/* Bulk controls */}
        <div className="flex items-center justify-between pt-0.5 text-[11px]">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleSelectAll}
            className="h-6 gap-1 px-1.5 text-xs text-accent hover:text-accent"
          >
            <CheckCheck className="size-3" /> Select All
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleClearAll}
            className="h-6 gap-1 px-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <RotateCcw className="size-3" /> Clear
          </Button>
        </div>
      </div>

      {/* Tree Content with dedicated scrollbar */}
      <div className="flex-1 min-h-0 space-y-1.5 overflow-y-scroll overflow-x-hidden overscroll-contain p-2 custom-scrollbar [scrollbar-gutter:stable]">
        {treeData.length === 0 ? (
          <div className="p-4 text-center text-xs text-muted-foreground">
            No POs or FGPNs available.
          </div>
        ) : (
          treeData.map(({ po, lines }) => {
            const isExpanded = expandedPos.has(po.id);
            const lineKeys = lines.map((l) => l.key);
            const checkedCount = lineKeys.filter((k) => selectedFgpnKeys.has(k)).length;
            const isAllChecked = lineKeys.length > 0 && checkedCount === lineKeys.length;
            const isIndeterminate = checkedCount > 0 && checkedCount < lineKeys.length;
            const project = findProject(po.projectId);

            return (
              <div
                key={po.id}
                className="overflow-hidden rounded-md border border-border bg-muted/10 transition-colors"
              >
                {/* PO Node */}
                <div className="flex items-center gap-1.5 px-2 py-1.5 hover:bg-muted/40">
                  <button
                    type="button"
                    onClick={() => toggleExpand(po.id)}
                    className="p-0.5 text-muted-foreground hover:text-foreground"
                    aria-label={isExpanded ? "Collapse PO" : "Expand PO"}
                  >
                    {isExpanded ? (
                      <ChevronDown className="size-3.5" />
                    ) : (
                      <ChevronRight className="size-3.5" />
                    )}
                  </button>

                  <input
                    type="checkbox"
                    ref={(el) => {
                      if (el) el.indeterminate = isIndeterminate;
                    }}
                    checked={isAllChecked}
                    onChange={() => handleSelectPo(po, lines, isAllChecked)}
                    className="size-3.5 rounded border-input text-accent focus:ring-accent accent-accent cursor-pointer"
                  />

                  {isExpanded ? (
                    <FolderOpen className="size-3.5 text-accent shrink-0" />
                  ) : (
                    <Folder className="size-3.5 text-muted-foreground shrink-0" />
                  )}

                  <div
                    role="button"
                    tabIndex={0}
                    onClick={() => toggleExpand(po.id)}
                    className="flex flex-1 min-w-0 items-center justify-between cursor-pointer select-none"
                  >
                    <div className="min-w-0 pr-1">
                      <div className="flex items-center gap-1">
                        <span className="font-mono text-xs font-semibold text-foreground truncate">
                          {po.poNumber}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          ({po.deliveryWeek})
                        </span>
                      </div>
                      <p className="text-[10px] text-muted-foreground truncate">
                        {po.jitCustomer} {project ? `· ${project.code}` : ""}
                      </p>
                    </div>

                    <Badge variant="outline" className="text-[10px] h-4 px-1 shrink-0 font-mono">
                      {checkedCount}/{lines.length}
                    </Badge>
                  </div>
                </div>

                {/* Underlying FGPN Nodes */}
                {isExpanded && (
                  <div className="border-t border-border/50 bg-background/60 pl-6 pr-2 py-1 space-y-1">
                    {lines.map((line) => {
                      const isChecked = selectedFgpnKeys.has(line.key);
                      return (
                        <div
                          key={line.id}
                          className="flex items-center gap-2 rounded px-1.5 py-1 text-xs hover:bg-muted/50 cursor-pointer"
                          onClick={() => handleToggleFgpn(line.key)}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => handleToggleFgpn(line.key)}
                            onClick={(e) => e.stopPropagation()}
                            className="size-3.5 rounded border-input text-accent focus:ring-accent accent-accent cursor-pointer"
                          />

                          <Box className="size-3 text-info shrink-0" />

                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-1">
                              <span className="font-mono text-[11px] font-medium text-foreground truncate">
                                {line.fgpn}
                              </span>
                              <span className="num text-[10px] text-foreground font-semibold">
                                {nf.format(line.remaining)} pcs
                              </span>
                            </div>
                            <p className="text-[10px] text-muted-foreground truncate">
                              {line.description ?? "Finished Good Item"}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Footer Info */}
      <div className="border-t border-border p-2 text-center text-[10px] text-muted-foreground shrink-0">
        Elementary simulation unit: <strong className="text-foreground">FGPN</strong>
      </div>
    </div>
  );
}
