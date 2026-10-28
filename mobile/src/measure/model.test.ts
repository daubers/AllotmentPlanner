import { nextToMeasure, type Item } from "./model";

const item = (id: number, over: Partial<Item> = {}): Item => ({
  id,
  feature_id: 1,
  feature_name: "Bed",
  feature_kind: "bed",
  kind: "edge",
  a: 0,
  b: 1,
  label: `${id}`,
  drawn_m: 1,
  value_m: null,
  note: "",
  skipped: false,
  stale: false,
  ...over,
});

test("the next item is the next unmeasured one after this", () => {
  const items = [item(1, { value_m: 2 }), item(2), item(3), item(4)];
  expect(nextToMeasure(items, 1)?.id).toBe(2);
  expect(nextToMeasure(items, 2)?.id).toBe(3);
});

test("it wraps round, and skips measured, skipped and stale ones", () => {
  const items = [item(1), item(2, { value_m: 1 }), item(3, { skipped: true }), item(4, { stale: true })];
  expect(nextToMeasure(items, 4)?.id).toBe(1);
  expect(nextToMeasure(items, 1)).toBeNull(); // nothing else left
});

test("when everything is done there is no next", () => {
  expect(nextToMeasure([item(1, { value_m: 1 })], 1)).toBeNull();
  expect(nextToMeasure([], 1)).toBeNull();
});
