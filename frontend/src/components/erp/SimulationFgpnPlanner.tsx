import { useEffect, useState } from "react";
import { GripVertical, Sliders, Sparkles, ArrowLeft, ArrowRight, RotateCcw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { nf } from "@/lib/erp/format";

export interface PlannerFgpnItem {
  id: string; // composite key `${poId}::${lineId}`
  poId: string;
  poNumber: string;
  lineId: string;
  fgpn: string;
  description?: string;
  defaultQty: number;
  simQty: number;
  priorityIndex: number;
  coveragePercent?: number; // 0 to 100
  launchableQty?: number;
}

interface SimulationFgpnPlannerProps {
  items: PlannerFgpnItem[];
  onItemsChange: (items: PlannerFgpnItem[]) => void;
}

export function SimulationFgpnPlanner({ items, onItemsChange }: SimulationFgpnPlannerProps) {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [simulateAll, setSimulateAll] = useState(false);

  useEffect(() => {
    if (!simulateAll) return;

    const needsReset = items.some((item) => item.simQty !== item.defaultQty);
    if (!needsReset) return;

    onItemsChange(
      items.map((item) => ({
        ...item,
        simQty: item.defaultQty,
      })),
    );
  }, [items, onItemsChange, simulateAll]);

  const handleMove = (index: number, direction: "left" | "right") => {
    const targetIndex = direction === "left" ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= items.length) return;

    const newItems = [...items];
    const [moved] = newItems.splice(index, 1);
    if (!moved) return;
    newItems.splice(targetIndex, 0, moved);

    const updated = newItems.map((item, idx) => ({
      ...item,
      priorityIndex: idx + 1,
    }));
    onItemsChange(updated);
  };

  const handleDragStart = (index: number) => {
    setDraggedIndex(index);
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;

    const newItems = [...items];
    const draggedItem = newItems[draggedIndex];
    if (!draggedItem) return;
    newItems.splice(draggedIndex, 1);
    newItems.splice(index, 0, draggedItem);

    setDraggedIndex(index);
    const updated = newItems.map((item, idx) => ({
      ...item,
      priorityIndex: idx + 1,
    }));
    onItemsChange(updated);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
  };

  const handleQtyChange = (id: string, val: string) => {
    const num = Number(val);
    const qty = isNaN(num) || num < 1 ? 1 : Math.floor(num);
    const updated = items.map((item) => (item.id === id ? { ...item, simQty: qty } : item));
    setSimulateAll(false);
    onItemsChange(updated);
  };

  const handleResetQuantities = () => {
    const updated = items.map((item) => ({
      ...item,
      simQty: item.defaultQty,
    }));
    onItemsChange(updated);
  };

  const handleSimulateAllChange = (checked: boolean | "indeterminate") => {
    const nextChecked = checked === true;
    setSimulateAll(nextChecked);
    if (!nextChecked) return;

    onItemsChange(
      items.map((item) => ({
        ...item,
        simQty: item.defaultQty,
      })),
    );
  };

  if (items.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col rounded-lg border border-border bg-card shadow-sm overflow-hidden mb-4">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-muted/40 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Sliders className="size-4 text-accent" />
          <div>
            <h3 className="text-xs font-semibold text-foreground">
              FGPN Order & Manual Quantity Entry
            </h3>
            <p className="text-[11px] text-muted-foreground">
              Reorder priority sequence and adjust simulation quantities simultaneously.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex h-7 items-center gap-1 rounded-md bg-accent px-2.5 text-xs font-semibold text-accent-foreground shadow-sm">
            <Sparkles className="size-3" />
            Order + Manual Entry
          </div>

          <label className="flex h-7 items-center gap-2 rounded-md border border-border bg-background px-2.5 text-xs font-medium text-foreground">
            <Checkbox checked={simulateAll} onCheckedChange={handleSimulateAllChange} />
            Simulate all
          </label>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleResetQuantities}
            className="h-7 text-xs text-muted-foreground hover:text-foreground"
          >
            <RotateCcw className="size-3 mr-1" /> Reset Qtys
          </Button>
        </div>
      </div>

      {/* Horizontal Carousel / Flex Strip of FGPN cards */}
      <div className="flex gap-3 overflow-x-auto p-3 bg-muted/10">
        {items.map((item, index) => {
          const isFull = (item.coveragePercent ?? 100) >= 100;
          const isPartial = (item.coveragePercent ?? 0) > 0 && (item.coveragePercent ?? 0) < 100;

          return (
            <div
              key={item.id}
              draggable
              onDragStart={() => handleDragStart(index)}
              onDragOver={(e) => handleDragOver(e, index)}
              onDragEnd={handleDragEnd}
              className={`flex flex-col justify-between min-w-[250px] max-w-[290px] shrink-0 rounded-md border border-border p-3 transition-all ${
                draggedIndex === index
                  ? "border-accent bg-accent/15 opacity-60 shadow-lg scale-95"
                  : "bg-card hover:border-accent/50 hover:shadow-sm"
              }`}
            >
              {/* Top Row: Priority Badge & Arrows */}
              <div className="flex items-center justify-between gap-1.5 pb-2 border-b border-border/50">
                <div className="flex items-center gap-1.5">
                  <div
                    className="cursor-grab text-muted-foreground hover:text-foreground active:cursor-grabbing p-0.5"
                    title="Drag left/right to reprioritize"
                  >
                    <GripVertical className="size-3.5" />
                  </div>
                  <Badge
                    variant="outline"
                    className="h-5 px-1.5 font-mono text-[10px] font-bold flex items-center gap-1 bg-accent/10 border-accent/30 text-accent-foreground"
                  >
                    Priority #{item.priorityIndex}
                  </Badge>
                </div>

                <div className="flex items-center gap-0.5">
                  <button
                    type="button"
                    disabled={index === 0}
                    onClick={() => handleMove(index, "left")}
                    className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground disabled:opacity-20"
                    title="Move Left (Higher Priority)"
                  >
                    <ArrowLeft className="size-3" />
                  </button>
                  <button
                    type="button"
                    disabled={index === items.length - 1}
                    onClick={() => handleMove(index, "right")}
                    className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground disabled:opacity-20"
                    title="Move Right (Lower Priority)"
                  >
                    <ArrowRight className="size-3" />
                  </button>
                </div>
              </div>

              {/* FGPN Core Details */}
              <div className="py-2.5 space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-bold text-foreground truncate">
                    {item.fgpn}
                  </span>
                  <Badge variant="secondary" className="h-4 px-1 text-[9px] font-mono shrink-0">
                    PO: {item.poNumber}
                  </Badge>
                </div>
                <p className="text-[11px] text-muted-foreground line-clamp-1">
                  {item.description ?? "Finished Good Item"}
                </p>
                <div className="text-[10px] text-muted-foreground">
                  PO Order Qty:{" "}
                  <strong className="text-foreground">{nf.format(item.defaultQty)}</strong> pcs
                </div>
              </div>

              {/* Bottom: Feasibility Badge & Quantity Control */}
              <div className="pt-2 border-t border-border/50 flex flex-col gap-2">
                {item.coveragePercent !== undefined && (
                  <div
                    className={`text-[10px] font-bold px-2 py-0.5 rounded text-center truncate ${
                      isFull
                        ? "bg-ok-soft text-ok border border-ok/20"
                        : isPartial
                          ? "bg-warn-soft text-warn border border-warn/20"
                          : "bg-danger-soft text-danger border border-danger/20"
                    }`}
                  >
                    {isFull
                      ? "100% Fully Covered"
                      : `${Math.round(item.coveragePercent)}% Covered (${nf.format(
                          item.launchableQty ?? 0,
                        )} / ${nf.format(item.simQty)} pcs)`}
                  </div>
                )}

                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-medium text-muted-foreground whitespace-nowrap">
                    Sim Qty:
                  </span>
                  {simulateAll ? (
                    <div className="flex h-7 min-w-24 items-center justify-end rounded-md border border-border bg-muted/30 px-2 font-mono text-xs font-bold text-foreground">
                      {nf.format(item.defaultQty)} pcs
                    </div>
                  ) : (
                    <Input
                      id={`qty-${item.id}`}
                      type="number"
                      min="1"
                      step="1"
                      value={item.simQty}
                      onChange={(e) => handleQtyChange(item.id, e.target.value)}
                      className="h-7 w-24 text-right font-mono text-xs bg-muted/20 font-bold"
                    />
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="border-t border-border bg-muted/20 px-3 py-1.5 text-[10px] text-muted-foreground flex flex-wrap items-center justify-between gap-2">
        <span>
          Stocks are sequentially allocated from{" "}
          <strong className="text-foreground">#1 (leftmost)</strong> to right until available stock
          is consumed.
        </span>
        <span className="font-semibold text-accent flex items-center gap-1">
          <ArrowRight className="size-3" /> Priority Chain Consumes Left-to-Right
        </span>
      </div>
    </div>
  );
}
