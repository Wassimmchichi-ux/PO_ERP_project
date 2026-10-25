import assert from "node:assert/strict";
import test from "node:test";
import { transitQuantitiesByTargetDate } from "../src/lib/erp/transitEligibility.ts";

const entry = (quantity, date, part = "MAT") => ({
  material_part_number: part,
  quantity,
  expected_arrival_date: date,
});

test("only confirmed positive arrivals up to and including the target count", () => {
  const stock = [
    entry("2.5", "2026-11-09"),
    entry(3, "2026-11-10"),
    entry(50, "2026-11-11"),
    entry(100, null),
    entry(0, "2026-11-09"),
    entry(-2, "2026-11-09"),
    entry("bad", "2026-11-09"),
    entry(4, "2026-11-10", "OTHER"),
  ];
  assert.deepEqual(
    [...transitQuantitiesByTargetDate(stock, "2026-11-10")],
    [
      ["MAT", 5.5],
      ["OTHER", 4],
    ],
  );
  assert.equal(transitQuantitiesByTargetDate(stock, "").size, 0);
});

test("changing either a supplier arrival or the target changes availability", () => {
  const stock = [entry(10, "2026-11-10")];
  assert.equal(transitQuantitiesByTargetDate(stock, "2026-11-10").get("MAT"), 10);
  stock[0].expected_arrival_date = "2026-11-12";
  assert.equal(transitQuantitiesByTargetDate(stock, "2026-11-10").size, 0);
  assert.equal(transitQuantitiesByTargetDate(stock, "2026-11-12").get("MAT"), 10);
});
