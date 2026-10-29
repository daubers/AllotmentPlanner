import { currentMonth, daysLabel, filterPackets, monthsLabel, packetTitle, photoFields, scanFields, sowableIn, toggleMonth } from "./model";

const tomato = { id: 1, name: "Tomato", variety: "Moneymaker", supplier: "Suttons", calendar: { sow_indoors: [2, 3], harvest: [8, 9] } };
const carrot = { id: 2, name: "Carrot", variety: "Nantes", supplier: "Thompson", latin_name: "Daucus carota", calendar: { sow_outdoors: [3, 4, 5] } };
const kale = { id: 3, name: "Kale", calendar: { plant_out: [5] }, notes: "good with tomato sauce" };

test("months read as runs, across the new year", () => {
  expect(monthsLabel([3, 4, 5, 9])).toBe("Mar to May, Sep");
  expect(monthsLabel([11, 12, 1, 2])).toBe("Nov to Feb");
  expect(monthsLabel([6])).toBe("Jun");
  expect(monthsLabel([])).toBe("");
  expect(monthsLabel([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])).toBe("All year");
});

test("toggling a month keeps the list sorted", () => {
  expect(toggleMonth([3, 9], 5)).toEqual([3, 5, 9]);
  expect(toggleMonth([3, 5, 9], 5)).toEqual([3, 9]);
  expect(toggleMonth(undefined, 2)).toEqual([2]);
});

test("sowable means indoors or outdoors, not planting out or harvest", () => {
  expect(sowableIn(tomato, 2)).toBe(true);
  expect(sowableIn(carrot, 4)).toBe(true);
  expect(sowableIn(tomato, 8)).toBe(false);
  expect(sowableIn(kale, 5)).toBe(false);
});

test("search matches name, variety, supplier, latin name and notes; sow-now narrows it", () => {
  const all = [tomato, carrot, kale];
  expect(filterPackets(all, { q: "tomato" }).map((p) => p.id)).toEqual([1, 3]);
  expect(filterPackets(all, { q: "DAUCUS" }).map((p) => p.id)).toEqual([2]);
  expect(filterPackets(all, { q: "thomp" }).map((p) => p.id)).toEqual([2]);
  expect(filterPackets(all, { month: 3 }).map((p) => p.id)).toEqual([1, 2]);
  expect(filterPackets(all, { month: 3, q: "carr" }).map((p) => p.id)).toEqual([2]);
  expect(filterPackets(all)).toHaveLength(3);
});

test("wording", () => {
  expect(packetTitle(tomato)).toBe("Tomato (Moneymaker)");
  expect(packetTitle(kale)).toBe("Kale");
  expect(daysLabel(7, 14)).toBe("7 to 14 days");
  expect(daysLabel(null, 21)).toBe("21 days");
  expect(daysLabel(null, null)).toBe("");
  expect(currentMonth(new Date(2026, 9, 29))).toBe(10);
});

test("photo upload fields", () => {
  expect(scanFields("c1")).toEqual({ read_packet: "true", client_id: "c1" });
  expect(photoFields({ trayId: 4 }, "c2")).toEqual({ client_id: "c2", tray_id: "4" });
  expect(photoFields({ plantingId: 9, packetId: 2 }, "c3")).toEqual({ client_id: "c3", packet_id: "2", planting_id: "9" });
});
