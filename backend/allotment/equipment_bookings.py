"""Equipment in use: when more is booked than you own. Pure, no database.

Same idea as the bed overbooking check in allotment.plan: sweep the days when bookings start or
end, add up the quantity in use between them, and report the stretches that exceed what you own.
A booking ends on the first day the equipment is free, so back to back bookings do not clash.
"""


def date_problem(starts_on, ends_on) -> str | None:
    """A message if the dates can't describe a stretch of use; None if they can."""
    if ends_on <= starts_on:
        return "The equipment must be free after the day it is first needed"
    return None


def booking_conflicts(bookings, quantity: int) -> list[dict]:
    """The stretches when the bookings need more than ``quantity`` of the item.

    Each result is {start, to, used, over, booking_ids}, ``to`` being the first day it is no longer
    over. Adjacent stretches with the same bookings are joined.
    """
    live = [b for b in bookings if b.starts_on < b.ends_on]
    days = sorted({b.starts_on for b in live} | {b.ends_on for b in live})
    found: list[dict] = []
    for start, stop in zip(days, days[1:], strict=False):
        active = [b for b in live if b.starts_on <= start and b.ends_on >= stop]
        used = sum(b.quantity for b in active)
        if used <= quantity:
            continue
        ids = sorted(b.id for b in active)
        last = found[-1] if found else None
        if last and last["to"] == start and last["booking_ids"] == ids:
            last["to"] = stop
            continue
        found.append(
            {"start": start, "to": stop, "used": used, "over": used - quantity, "booking_ids": ids}
        )
    return found


def overlapping(conflicts: list[dict], booking) -> list[dict]:
    """Only the conflicts this booking is part of (what to warn about when it is saved)."""
    return [c for c in conflicts if booking.id in c["booking_ids"]]
