interface DatedTransitQuantity {
  material_part_number: string;
  quantity: string | number;
  expected_arrival_date: string | null;
}

export function transitQuantitiesByTargetDate(
  entries: readonly DatedTransitQuantity[],
  targetDate: string,
): Map<string, number> {
  const quantities = new Map<string, number>();
  if (!targetDate) return quantities;
  for (const entry of entries) {
    if (!entry.expected_arrival_date || entry.expected_arrival_date > targetDate) continue;
    const quantity = Number(entry.quantity);
    if (!Number.isFinite(quantity) || quantity <= 0) continue;
    quantities.set(
      entry.material_part_number,
      (quantities.get(entry.material_part_number) ?? 0) + quantity,
    );
  }
  return quantities;
}
