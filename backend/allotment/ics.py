"""Turn visits into iCalendar (.ics) data: a single event, or a feed of several."""

from datetime import timedelta
from urllib.parse import urlparse

from flask import current_app
from icalendar import Alarm, Calendar, Event

from .models import Task, Visit


def _host() -> str:
    """The host to qualify UIDs with, so they're stable even if PUBLIC_URL's scheme changes."""
    public_url = current_app.config.get("PUBLIC_URL", "")
    return urlparse(public_url).netloc or "allotment.local"


def _uid(visit: Visit) -> str:
    return f"visit-{visit.id}@{_host()}"


def _vevent(visit: Visit, tasks: list[Task], bring: list[str] | None = None) -> Event:
    event = Event()
    event.add("uid", _uid(visit))
    event.add("dtstamp", visit.updated_at)
    event.add("dtstart", visit.starts_at)
    event.add("dtend", visit.starts_at + timedelta(minutes=visit.duration_minutes))
    # A whole number of seconds since epoch so an edit always bumps it, even sub-second ones.
    event.add("sequence", int(visit.updated_at.timestamp()))
    event.add("summary", visit.title)

    description = visit.notes.strip()
    if tasks:
        checklist = "\n".join(f"- {t.title}" for t in tasks)
        description = f"{description}\n\n{checklist}" if description else checklist
    if bring:
        tools = f"Bring: {', '.join(bring)}"
        description = f"{description}\n\n{tools}" if description else tools
    if description:
        event.add("description", description)

    public_url = current_app.config.get("PUBLIC_URL", "")
    if public_url:
        event.add("url", f"{public_url}/allotments/{visit.allotment_id}/visits/{visit.id}")

    alarm = Alarm()
    alarm.add("action", "DISPLAY")
    alarm.add("description", visit.title)
    alarm.add("trigger", timedelta(hours=-1))
    event.add_component(alarm)

    return event


def visit_to_ics(visit: Visit, tasks: list[Task], bring: list[str] | None = None) -> bytes:
    """A single-event calendar, for downloading one visit. ``bring`` names the equipment to take."""
    cal = Calendar()
    cal.add("prodid", "-//Allotment Planner//visits//EN")
    cal.add("version", "2.0")
    cal.add_component(_vevent(visit, tasks, bring))
    return cal.to_ical()


def feed_to_ics(entries: list[tuple]) -> bytes:
    """A VCALENDAR of every visit, for a webcal subscription.

    Each entry is (visit, tasks) or (visit, tasks, bring names).
    """
    cal = Calendar()
    cal.add("prodid", "-//Allotment Planner//visits//EN")
    cal.add("version", "2.0")
    for visit, tasks, *rest in entries:
        cal.add_component(_vevent(visit, tasks, rest[0] if rest else None))
    return cal.to_ical()
