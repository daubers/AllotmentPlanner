"""Recurring tasks on a schedule: which dates a series covers. Pure, no database.

A series is a rule (every N days, weeks or months from a start until an end). Its occurrences are
ordinary tasks, created in advance. Dates are always worked out from the start date, not from the
previous occurrence, so a monthly job on the 31st goes back to the 31st after a short month.
"""

import calendar
from datetime import date, timedelta

UNITS = ("day", "week", "month")
MAX_OCCURRENCES = 366


def add_months(d: date, months: int) -> date:
    """``d`` moved by whole months; the day of the month stays, or is the last if it is shorter."""
    index = d.year * 12 + (d.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def step(d: date, n: int, unit: str) -> date:
    """``d`` plus ``n`` days, weeks or months."""
    if unit == "day":
        return d + timedelta(days=n)
    if unit == "week":
        return d + timedelta(weeks=n)
    if unit == "month":
        return add_months(d, n)
    raise ValueError(f"unknown unit {unit!r}")


def occurrences(
    starts_on: date, until_on: date, every_n: int, unit: str, not_before: date | None = None
) -> list[date]:
    """Every date from ``starts_on`` to ``until_on`` inclusive, those from ``not_before`` on.

    Raises ValueError if the whole series (past dates included) is longer than MAX_OCCURRENCES.
    """
    dates, k = [], 0
    while (d := step(starts_on, k * every_n, unit)) <= until_on:
        if len(dates) >= MAX_OCCURRENCES:
            raise ValueError(f"A series can have at most {MAX_OCCURRENCES} occurrences")
        dates.append(d)
        k += 1
    return [d for d in dates if not_before is None or d >= not_before]


def occurrence_key(series_id: int, d: date) -> str:
    """The task's ``suggestion_key``: it stops one date being created twice."""
    return f"series:{series_id}:{d.isoformat()}"


def describe(every_n: int, unit: str) -> str:
    """ "every day", "every 2 weeks", "every month"."""
    return f"every {unit}" if every_n == 1 else f"every {every_n} {unit}s"
