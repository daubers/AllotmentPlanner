"""Domain event bus.

Every state change calls ``emit``; behaviour such as activity logging, metrics or
Mastodon posting is added by registering a subscriber, not by editing call sites.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import structlog

log = structlog.get_logger(__name__)

WILDCARD = "*"


@dataclass(frozen=True)
class Event:
    type: str
    actor_id: int | None = None
    allotment_id: int | None = None
    subject: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


Subscriber = Callable[[Event], None]
_subscribers: dict[str, list[Subscriber]] = defaultdict(list)


def subscribe(event_type: str, fn: Subscriber) -> Subscriber:
    """Register ``fn`` for an event type, or ``"*"`` for all events."""
    _subscribers[event_type].append(fn)
    return fn


def clear_subscribers() -> None:
    _subscribers.clear()


def emit(event_type: str, **kwargs: Any) -> Event:
    event = Event(type=event_type, **kwargs)
    for fn in [*_subscribers[event_type], *_subscribers[WILDCARD]]:
        try:
            fn(event)
        except Exception:  # a failing subscriber must never break the request
            log.exception("event_subscriber_failed", event_type=event_type, subscriber=fn.__name__)
    return event
