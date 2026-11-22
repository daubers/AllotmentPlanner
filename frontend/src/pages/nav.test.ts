import { describe, expect, it } from "vitest";
import { groupFor, NAV, sectionOf } from "./nav";

describe("allotment menu", () => {
  it("lists every page once, under one group", () => {
    const pages = NAV.flatMap((g) => g.pages.map((p) => p.to));
    expect(new Set(pages).size).toBe(pages.length);
    expect(pages.sort()).toEqual(["", "beds", "layers", "notes", "overview", "photos", "seeds", "tasks", "today", "trays", "visits"]);
  });

  it("has unique labels", () => {
    const labels = [...NAV.map((g) => g.label), ...NAV.flatMap((g) => g.pages.map((p) => p.label))];
    expect(new Set(labels).size).toBe(labels.length);
  });

  it("puts each page in the agreed group", () => {
    const by = (path: string) => groupFor(`/allotments/3${path}`);
    expect(by("")).toBe("plot");
    expect(by("/")).toBe("plot");
    expect(by("/layers")).toBe("plot");
    expect(["/seeds", "/trays", "/beds"].map(by)).toEqual(["grow", "grow", "grow"]);
    expect(["/today", "/tasks", "/visits"].map(by)).toEqual(["work", "work", "work"]);
    expect(["/photos", "/notes", "/overview"].map(by)).toEqual(["record", "record", "record"]);
  });

  it("keeps detail pages with their list", () => {
    expect(groupFor("/allotments/3/seeds/12")).toBe("grow");
    expect(groupFor("/allotments/3/beds/5")).toBe("grow");
    expect(groupFor("/allotments/3/trays/1")).toBe("grow");
  });

  it("gives Settings no group, and an unknown page the first", () => {
    expect(groupFor("/allotments/3/settings")).toBeNull();
    expect(groupFor("/allotments/3/nope")).toBe("plot");
  });

  it("reads the section from a path", () => {
    expect(sectionOf("/allotments/10/seeds/2")).toBe("seeds");
    expect(sectionOf("/allotments/10")).toBe("");
  });
});
