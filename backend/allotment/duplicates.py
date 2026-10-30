"""Spotting the same file uploaded twice.

Two copies of one video make OpenSfM see two cameras at every place, and the map falls apart into
pieces. There is no content hash to compare, so a copy is a file of the same kind with exactly the
same size, length and dimensions: close enough that two different recordings never match.
"""

from collections.abc import Iterable

from .models import Media


def _fingerprint(m: Media) -> tuple | None:
    if not m.size_bytes:
        return None  # nothing to compare yet
    duration = round(m.duration_s, 1) if m.duration_s is not None else None
    return (m.kind, m.size_bytes, duration, m.width, m.height)


def duplicates_of(media: Iterable[Media]) -> dict[int, int]:
    """Map each later copy's id to the id of the earliest upload it repeats."""
    first: dict[tuple, int] = {}
    copies: dict[int, int] = {}
    for m in sorted(media, key=lambda m: m.id):
        key = _fingerprint(m)
        if key is None:
            continue
        if key in first:
            copies[m.id] = first[key]
        else:
            first[key] = m.id
    return copies
