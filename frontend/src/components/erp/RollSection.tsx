import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Section } from "@/components/erp/PageHeader";

export interface RollItem {
  id: string;
  rollSize: string;
  numberOfRolls: string;
}

export function RollSection({
  initialRolls = [
    { id: "roll-1", rollSize: "", numberOfRolls: "" },
    { id: "roll-2", rollSize: "", numberOfRolls: "" },
  ],
  onChange,
}: {
  initialRolls?: RollItem[];
  onChange?: (rolls: RollItem[]) => void;
}) {
  const [rolls, setRolls] = useState<RollItem[]>(initialRolls);

  const handleUpdate = (id: string, field: "rollSize" | "numberOfRolls", value: string) => {
    const updated = rolls.map((roll) => (roll.id === id ? { ...roll, [field]: value } : roll));
    setRolls(updated);
    onChange?.(updated);
  };

  const handleAddRoll = () => {
    const newRoll: RollItem = {
      id: `roll-${Date.now()}`,
      rollSize: "",
      numberOfRolls: "",
    };
    const updated = [...rolls, newRoll];
    setRolls(updated);
    onChange?.(updated);
  };

  const handleRemoveRoll = (id: string) => {
    if (rolls.length <= 1) return;
    const updated = rolls.filter((roll) => roll.id !== id);
    setRolls(updated);
    onChange?.(updated);
  };

  return (
    <div className="space-y-4">
      {rolls.map((roll, index) => (
        <Section
          key={roll.id}
          title={`Roll Details #${index + 1}`}
          actions={
            rolls.length > 1 ? (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-7 text-muted-foreground hover:text-destructive"
                onClick={() => handleRemoveRoll(roll.id)}
                aria-label={`Remove Roll #${index + 1}`}
              >
                <Trash2 className="size-4" />
              </Button>
            ) : null
          }
        >
          <div className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor={`roll-size-${roll.id}`}>Roll Size</Label>
              <Input
                id={`roll-size-${roll.id}`}
                placeholder="e.g. 1000mm or 50m"
                value={roll.rollSize}
                onChange={(e) => handleUpdate(roll.id, "rollSize", e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={`num-rolls-${roll.id}`}>Number of Rolls</Label>
              <Input
                id={`num-rolls-${roll.id}`}
                type="number"
                min="1"
                placeholder="e.g. 10"
                value={roll.numberOfRolls}
                onChange={(e) => handleUpdate(roll.id, "numberOfRolls", e.target.value)}
              />
            </div>
          </div>
        </Section>
      ))}

      <div className="flex justify-start">
        <Button
          type="button"
          variant="outline"
          onClick={handleAddRoll}
          className="flex items-center gap-1.5 text-xs font-medium"
        >
          <Plus className="size-3.5" />
          Add Roll Section
        </Button>
      </div>
    </div>
  );
}

export default RollSection;
