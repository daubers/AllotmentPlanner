import { describe, expect, it } from "vitest";
import { bookingConflicts, involving } from "./conflicts";

const b = (id: number, quantity: number, starts_on: string, ends_on: string) => ({ id, quantity, starts_on, ends_on });

// These mirror backend/tests/test_equipment_bookings.py so the two checks cannot drift apart.
describe("bookingConflicts", () => {
  it("is empty when you own enough, or nothing is booked", () => {
    expect(bookingConflicts([b(1, 3, "2026-03-01", "2026-05-01"), b(2, 3, "2026-04-01", "2026-06-01")], 6)).toEqual([]);
    expect(bookingConflicts([], 6)).toEqual([]);
  });

  it("reports six cloches covering eight", () => {
    expect(bookingConflicts([b(1, 5, "2026-03-01", "2026-05-01"), b(2, 3, "2026-04-01", "2026-06-01")], 6)).toEqual([
      { from: "2026-04-01", to: "2026-05-01", used: 8, over: 2, bookingIds: [1, 2] },
    ]);
  });

  it("does not count back to back bookings as a clash", () => {
    expect(bookingConflicts([b(1, 6, "2026-03-01", "2026-04-01"), b(2, 6, "2026-04-01", "2026-05-01")], 6)).toEqual([]);
  });

  it("separates stretches with different bookings and joins those with the same", () => {
    const got = bookingConflicts([b(1, 4, "2026-03-01", "2026-09-01"), b(2, 4, "2026-04-01", "2026-06-01"), b(3, 1, "2026-05-01", "2026-05-15")], 6);
    expect(got.map((g) => [g.from, g.to, g.bookingIds, g.used])).toEqual([
      ["2026-04-01", "2026-05-01", [1, 2], 8],
      ["2026-05-01", "2026-05-15", [1, 2, 3], 9],
      ["2026-05-15", "2026-06-01", [1, 2], 8],
    ]);
  });

  it("finds just the clashes a booking is part of", () => {
    const conflicts = bookingConflicts([b(1, 5, "2026-03-01", "2026-04-01"), b(2, 3, "2026-03-15", "2026-04-01"), b(3, 6, "2026-08-01", "2026-09-01"), b(4, 1, "2026-08-01", "2026-09-01")], 6);
    expect(conflicts.map((c) => c.bookingIds)).toEqual([[1, 2], [3, 4]]);
    expect(involving(conflicts, 1)).toEqual([conflicts[0]]);
    expect(involving(conflicts, 4)).toEqual([conflicts[1]]);
    expect(involving(conflicts, 9)).toEqual([]);
  });
});
