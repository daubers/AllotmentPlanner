import { applyLocally, countsOf, cellMap, cellsRequest, colourFor, describeCell, glyph, key, KIND_COLOURS, posOf, summarise, toggle, toggleCol, toggleRow } from "./model";

test("selection", () => {
  expect([...toggle(new Set(), key(1, 2))]).toEqual(["1,2"]);
  expect(toggle(new Set(["1,2"]), "1,2").size).toBe(0);
  expect([...toggleRow(new Set(), 1, 3)].sort()).toEqual(["1,0", "1,1", "1,2"]);
  expect(toggleRow(toggleRow(new Set(), 1, 3), 1, 3).size).toBe(0);
  expect([...toggleCol(new Set(["0,2"]), 2, 3)].sort()).toEqual(["0,2", "1,2", "2,2"]);
  expect(posOf("1,2")).toEqual({ row: 1, col: 2 });
});

test("wording", () => {
  expect(summarise({ sown: 5, germinated: 2, failed: 0, planted_out: 0, empty: 4 })).toBe("5 sown, 2 came up, 4 empty");
  expect(summarise(undefined)).toBe("");
  expect(describeCell(0, 1, undefined)).toBe("Row 1, column 2: empty");
  expect(describeCell(0, 1, { row: 0, col: 1, status: "germinated" }, "Tomato")).toBe("Row 1, column 2: Tomato, came up");
  expect(glyph({ row: 0, col: 0, status: "germinated" })).toBe("✓");
  expect(glyph({ row: 0, col: 0, status: "failed" })).toBe("✕");
  expect(glyph({ row: 0, col: 0, status: "sown", count: 3 })).toBe("3");
  expect(glyph(undefined)).toBe("");
});

test("each kind of seed keeps its colour", () => {
  const kinds = [{ packet_id: 5 }, { packet_id: 9 }];
  expect(colourFor(5, kinds)).toBe(KIND_COLOURS[0]);
  expect(colourFor(9, kinds)).toBe(KIND_COLOURS[1]);
  expect(colourFor(null, kinds)).toBeNull();
  expect(colourFor(77, kinds)).toBeNull();
});

test("the queued request carries the chosen cells", () => {
  expect(cellsRequest(3, 1, new Set(["0,0", "0,1"]), { status: "germinated" })).toEqual({
    method: "PATCH",
    path: "/api/v1/allotments/1/trays/3/cells",
    body: { cells: [{ row: 0, col: 0 }, { row: 0, col: 1 }], set: { status: "germinated" } },
  });
});

describe("applying a change on screen before the server confirms", () => {
  const cells = [
    { row: 0, col: 0, packet_id: 7, count: 1, status: "sown" },
    { row: 0, col: 1, packet_id: 7, count: 1, status: "planted_out" },
  ];
  test("sowing an empty cell", () => {
    const out = applyLocally(cells, new Set(["1,0"]), { packet_id: 9, count: 2 });
    expect(cellMap(out).get("1,0")).toMatchObject({ packet_id: 9, count: 2, status: "sown" });
  });
  test("coming up, failing and clearing", () => {
    expect(cellMap(applyLocally(cells, new Set(["0,0"]), { status: "germinated" })).get("0,0")?.status).toBe("germinated");
    expect(cellMap(applyLocally(cells, new Set(["0,0"]), { status: "failed" })).get("0,0")?.status).toBe("failed");
    expect(cellMap(applyLocally(cells, new Set(["0,0"]), { status: "empty" })).has("0,0")).toBe(false);
  });
  test("an empty cell cannot come up, and a planted-out cell is left alone", () => {
    expect(cellMap(applyLocally(cells, new Set(["1,2"]), { status: "germinated" })).has("1,2")).toBe(false);
    expect(cellMap(applyLocally(cells, new Set(["0,1"]), { status: "failed" })).get("0,1")?.status).toBe("planted_out");
  });
});

test("counts follow the cells", () => {
  const cells = [
    { row: 0, col: 0, status: "sown" },
    { row: 0, col: 1, status: "germinated" },
    { row: 1, col: 0, status: "failed" },
    { row: 1, col: 1, status: "planted_out" },
  ];
  expect(countsOf(2, 3, cells)).toEqual({ empty: 2, sown: 1, germinated: 1, failed: 1, planted_out: 1 });
});
