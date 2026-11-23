import { describe, expect, it } from "vitest";
import type { Crop, Packet } from "./basis";
import { basisFromCrop, basisFromPacket, defaultDates } from "./basis";

const lettuce: Crop = {
  key: "lettuce", name: "Lettuce", method_default: "direct_sow", spacing_plant_cm: 30, spacing_row_cm: 30,
  maturity_days_min: 50, maturity_days_max: 70, sow_months: [3, 4, 5, 6, 7, 8], plant_out_months: [],
  harvest_months: [5, 6, 7, 8, 9, 10], succession_days: 14,
};
const tomato: Crop = {
  key: "tomato", name: "Tomato", method_default: "transplant", spacing_plant_cm: 45, spacing_row_cm: 60,
  maturity_days_min: 100, maturity_days_max: 130, sow_months: [2, 3, 4], plant_out_months: [5, 6],
  harvest_months: [7, 8, 9, 10], succession_days: null,
};

describe("basis from a crop", () => {
  it("copies the crop's figures", () => {
    const b = basisFromCrop(lettuce);
    expect(b).toMatchObject({ name: "Lettuce", cropKey: "lettuce", packetId: null, method: "direct_sow", successionDays: 14 });
    expect(b.spacing).toEqual({ plant: 30, row: 30 });
  });
});

describe("basis from a packet", () => {
  const packet: Packet = { id: 7, name: "Lettuce", variety: "Little Gem", calendar: { sow_outdoors: [4, 5, 6] } };

  it("uses the packet's own months and names the variety", () => {
    const b = basisFromPacket(packet);
    expect(b).toMatchObject({ name: "Lettuce (Little Gem)", packetId: 7, method: "direct_sow", sowMonths: [4, 5, 6] });
    expect(b.maturityMax).toBe(90); // no figures anywhere: a plain default
    expect(b.spacing).toEqual({ plant: null, row: null });
  });

  it("fills the gaps from a crop but keeps what the packet says", () => {
    const b = basisFromPacket({ ...packet, spacing_plant_cm: 20 }, lettuce);
    expect(b.spacing).toEqual({ plant: 20, row: 30 });
    expect(b.maturityMax).toBe(70);
    expect(b.cropKey).toBe("lettuce");
    expect(b.sowMonths).toEqual([4, 5, 6]);
  });

  it("is a transplant when it is only sown indoors", () => {
    const b = basisFromPacket({ id: 1, name: "Tomato", calendar: { sow_indoors: [2, 3], plant_out: [5] } });
    expect(b).toMatchObject({ method: "transplant", sowMonths: [2, 3], plantOutMonths: [5] });
  });
});

describe("default dates", () => {
  it("sows in the next window and clears the bed at maturity", () => {
    expect(defaultDates(basisFromCrop(lettuce), "2026-01-10")).toEqual({ sow_on: "2026-03-01", plant_out_on: null, end_on: "2026-05-10" });
    expect(defaultDates(basisFromCrop(lettuce), "2026-04-10").sow_on).toBe("2026-04-10");
  });

  it("brings a transplant out after its tray time, in its plant-out months", () => {
    const d = defaultDates(basisFromCrop(tomato), "2026-02-10");
    expect(d.sow_on).toBe("2026-02-10");
    expect(d.plant_out_on).toBe("2026-05-01"); // 28 days later is March; May is the first plant-out month
    expect(d.end_on).toBe("2026-06-20"); // sown + 130 days
  });

  it("always leaves a transplant a month in the bed", () => {
    const d = defaultDates({ ...basisFromCrop(tomato), maturityMax: 40 }, "2026-02-10");
    expect(d.end_on >= "2026-05-31").toBe(true);
  });

  it("falls back to today when there are no sowing months", () => {
    expect(defaultDates({ ...basisFromCrop(lettuce), sowMonths: [] }, "2026-07-04").sow_on).toBe("2026-07-04");
  });
});
