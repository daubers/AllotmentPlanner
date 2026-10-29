"""Reads the facts off the text of a seed packet. Pure: text in, fields out, no model, no I/O.

The text comes from an OCR engine (see docs/seed-scanning-spike.md) and is untidy: lines in odd
orders, letters misread, units attached or detached. Every finder returns None when it is not sure,
because a blank in the draft is better than a wrong value the user might not notice.
"""

import re
from dataclasses import dataclass, field
from datetime import date

MONTHS = [
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
]
_MONTH = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
SUPPLIERS = {
    "Mr Fothergill's": ("fothergill",),
    "Suttons": ("suttons",),
    "Johnsons": ("johnsons",),
    "Thompson & Morgan": ("thompson & morgan", "thompson and morgan", "t&m"),
    "Marshalls": ("marshalls",),
    "Kings Seeds": ("kings seeds",),
    "Dobies": ("dobies",),
    "Unwins": ("unwins",),
}


def month_number(word: str) -> int | None:
    key = word.strip().lower()[:3]
    return MONTHS.index(key) + 1 if key in MONTHS else None


def _num(text: str) -> float:
    return float(text.replace(",", "."))


def find_depth_mm(text: str) -> int | None:
    """Sowing depth in millimetres, from "1.5cm (1/2") deep", "depth of 13mm", "5cm deep"."""
    t = text.replace("\n", " ")
    patterns = [
        r"(\d+(?:[.,]\d+)?)\s?(mm|cm)\b[^.]{0,30}?\bdeep",
        r"\bdepth\s+of\s+(\d+(?:[.,]\d+)?)\s?(mm|cm)\b",
        r"\bdeep\b[^.\d]{0,10}(\d+(?:[.,]\d+)?)\s?(mm|cm)\b",
        r"\bsow(?:ing)?\b[^.]{0,40}?(\d+(?:[.,]\d+)?)\s?(mm|cm)\s*\(",
    ]
    for pattern in patterns:
        m = re.search(pattern, t, re.I)
        if m:
            value = _num(m.group(1)) * (10 if m.group(2).lower() == "cm" else 1)
            return round(value) if 0 < value <= 500 else None
    return None


def find_germination_days(text: str) -> tuple[int, int] | None:
    """Days to germinate as (min, max): "appear in 14-21 days", "Germination 15-20 days"."""
    t = text.replace("\n", " ")
    m = re.search(
        r"(?:appear|germinat\w*|emerge|sprout)[^.\d]{0,40}(\d+)\s*(?:-|–|—|to)\s*(\d+)\s*days",
        t,
        re.I,
    )
    if m and int(m.group(1)) <= int(m.group(2)) <= 120:
        return int(m.group(1)), int(m.group(2))
    m = re.search(
        r"(?:appear|germinat\w*|emerge|sprout)[^.\d]{0,40}(?:about|around|in)?\s*(\d+)\s*days",
        t,
        re.I,
    )
    if m and 0 < int(m.group(1)) <= 120:
        return int(m.group(1)), int(m.group(1))
    return None


def find_sow_by_year(text: str, today: date | None = None) -> int | None:
    """The "sow by" year: "Sow by DEC 2027", "SOW BY YE 2028", "Sow by: 7/2024"."""
    t = text.replace("\n", " ")
    m = re.search(
        rf"sow\s*by\W{{0,12}}(?:ye\s*)?(?:{_MONTH}\s*)?(?:\d{{1,2}}\s*/\s*)?(20\d\d)",
        t,
        re.I,
    )
    if not m:
        m = re.search(
            rf"best\s*before\W{{0,12}}(?:end\s*)?(?:{_MONTH}\s*)?(?:\d{{1,2}}\s*/\s*)?(20\d\d)",
            t,
            re.I,
        )
    if not m:
        return None
    year = int(m.group(m.lastindex))
    return year if 2000 <= year <= (today or date.today()).year + 15 else None


def find_seed_count(text: str) -> int | None:
    """ "Average 500 seeds", "Average Contents 70 Seeds", "250 seeds"."""
    t = text.replace("\n", " ")
    m = re.search(
        r"(?:average|avg)\W{0,6}(?:contents?\W{0,3})?(\d[\d,]*)\s*seeds?", t, re.I
    ) or re.search(r"\b(\d[\d,]{1,5})\s*seeds\b", t, re.I)
    if not m:
        return None
    count = int(m.group(1).replace(",", ""))
    return count if 1 <= count <= 100000 else None


def find_supplier(text: str) -> str | None:
    low = text.lower().replace("’", "'")
    for name, needles in SUPPLIERS.items():
        if any(n in low for n in needles):
            return name
    return None


def months_in(text: str) -> list[int]:
    """Months named in a phrase: "March to June" is 3 to 6, "Nov to Feb" wraps, "all year" is all."""
    low = text.lower()
    if re.search(r"all\s+year(?:\s+round)?|throughout the year|year[- ]round", low):
        return list(range(1, 13))
    found: set[int] = set()
    for m in re.finditer(rf"{_MONTH}\s*(?:to|-|–|—|until|through)\s*{_MONTH}", low):
        a, b = month_number(m.group(1)), month_number(m.group(2))
        if a and b:
            span = range(a, b + 1) if a <= b else [*range(a, 13), *range(1, b + 1)]
            found.update(span)
    covered = re.sub(rf"{_MONTH}\s*(?:to|-|–|—|until|through)\s*{_MONTH}", " ", low)
    for m in re.finditer(rf"\b{_MONTH}\b(\s+onwards)?", covered):
        n = month_number(m.group(1))
        if n:
            found.update(range(n, 13) if m.group(2) else [n])
    return sorted(found)


def months_from_words(text: str) -> dict[str, list[int]]:
    """The calendar of a packet that has no graphic, from lines like "When  March to June".

    Handles the "For outdoor sowing / For indoor sowing" blocks with When and Harvest rows.
    Only what is stated is returned; an activity with no months is left out.
    """
    out: dict[str, set[int]] = {}
    section = None
    for raw in text.splitlines():
        line = raw.strip()
        low = line.lower()
        if "outdoor sowing" in low or "sow outdoors" in low and len(line) < 40:
            section = "sow_outdoors"
        elif "indoor sowing" in low or "sow indoors" in low and len(line) < 40:
            section = "sow_indoors"
        elif low.startswith("when") and section:
            out.setdefault(section, set()).update(months_in(line[4:]))
        elif low.startswith("harvest"):
            out.setdefault("harvest", set()).update(months_in(line[7:]))
    return {k: sorted(v) for k, v in out.items() if v}


@dataclass
class PacketFacts:
    supplier: str | None = None
    seeds_in_packet: int | None = None
    sow_depth_mm: int | None = None
    germinate_days_min: int | None = None
    germinate_days_max: int | None = None
    best_before_year: int | None = None
    calendar_words: dict[str, list[int]] = field(default_factory=dict)

    def missing(self) -> list[str]:
        """Names of the fields we could not find, so the draft can say so."""
        names = ["supplier", "seeds_in_packet", "sow_depth_mm", "best_before_year"]
        gone = [n for n in names if getattr(self, n) is None]
        if self.germinate_days_min is None:
            gone.append("germinate_days")
        return gone


def parse_packet_text(text: str, today: date | None = None) -> PacketFacts:
    germ = find_germination_days(text)
    return PacketFacts(
        supplier=find_supplier(text),
        seeds_in_packet=find_seed_count(text),
        sow_depth_mm=find_depth_mm(text),
        germinate_days_min=germ[0] if germ else None,
        germinate_days_max=germ[1] if germ else None,
        best_before_year=find_sow_by_year(text, today),
        calendar_words=months_from_words(text),
    )
