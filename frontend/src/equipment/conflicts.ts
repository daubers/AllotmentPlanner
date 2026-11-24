import { toDay } from "../plan/dates";

type Slot = { id: number; quantity: number; starts_on: string; ends_on: string };
export type Overbooked = { from: string; to: string; used: number; over: number; bookingIds: number[] };

/**
 * When the bookings need more of an item than you own. The same sweep as the server's (and the
 * bed overbooking check): a booking ends on the first day the item is free, so back to back is fine.
 * Lets the booking dialog warn before anything is saved.
 */
export function bookingConflicts(bookings: Slot[], owned: number): Overbooked[] {
  const live = bookings.filter((b) => toDay(b.starts_on) < toDay(b.ends_on));
  const days = [...new Set(live.flatMap((b) => [b.starts_on, b.ends_on]))].sort();
  const found: Overbooked[] = [];
  for (let i = 0; i + 1 < days.length; i++) {
    const [start, stop] = [days[i], days[i + 1]];
    const active = live.filter((b) => b.starts_on <= start && b.ends_on >= stop);
    const used = active.reduce((n, b) => n + b.quantity, 0);
    if (used <= owned) continue;
    const ids = active.map((b) => b.id).sort((a, b) => a - b);
    const last = found[found.length - 1];
    if (last && last.to === start && last.bookingIds.join() === ids.join()) last.to = stop;
    else found.push({ from: start, to: stop, used, over: used - owned, bookingIds: ids });
  }
  return found;
}

/** Only the clashes a given booking is part of. */
export const involving = (conflicts: Overbooked[], id: number) => conflicts.filter((c) => c.bookingIds.includes(id));
