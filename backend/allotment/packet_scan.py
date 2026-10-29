"""Turns a photo of the back of a seed packet into a draft of its details.

Orchestration over three readers, none of which need a database: the colour-bar calendar read from
pixels (``calendar_cv``), the text read by an OCR engine (``ocr``) and parsed (``packet_text``), and
a guess at the name and variety. Everything it could not find is listed, so the draft can say so:
a blank beats a wrong value the user might not notice.
"""

import re
from dataclasses import dataclass, field
from datetime import date

from PIL import Image

from . import ocr
from .packet_text import PacketFacts, parse_packet_text
from .seeds import normalise_calendar

# Words that are never the plant's name even when printed large.
NOT_A_NAME = re.compile(
    r"seeds?|average|contents?|sow|harvest|indoors|outdoors|plant out|suttons|fothergill|johnsons"
    r"|thompson|morgan|marshalls|quality|guarantee|seedling|growing|packed|www\.|\.co\.uk|f1 hybrid"
    r"|for more|standard|promotional|to sow|grow",
    re.I,
)
MAX_NAME_CHARS = 40


@dataclass
class ScanResult:
    name: str | None = None
    variety: str | None = None
    facts: PacketFacts = field(default_factory=PacketFacts)
    calendar: dict[str, list[int]] = field(default_factory=dict)
    calendar_source: str | None = None  # graphic | words | None
    calendar_crop: Image.Image | None = None
    rotation: int = 0
    raw_text: str = ""
    missing: list[str] = field(default_factory=list)


PLANTS = sorted(
    """carrot parsley coriander cilantro dill cabbage lettuce rocket cress mustard borage pea peas
    mangetout bean beans broad bean runner bean french bean beetroot radish spinach chard kale
    cauliflower broccoli sprouts brussels sprout leek onion spring onion shallot garlic tomato
    cucumber courgette marrow squash pumpkin sweetcorn pepper chilli aubergine celery celeriac
    fennel basil chives mint thyme sage oregano rosemary marjoram lavender sunflower nasturtium
    marigold calendula cosmos zinnia sweet pea poppy cornflower nigella foxglove aster lupin swede
    turnip parsnip kohlrabi pak choi mizuna endive chicory radicchio rhubarb strawberry melon
    potato leaf salad salad mix lamb's lettuce mache sorrel chervil camomile chamomile sweet william
    wallflower pansy viola petunia lobelia alyssum sweet alyssum antirrhinum snapdragon stock
    sweet corn butternut sorrel land cress rocket wild rocket""".replace("\n", " ").split(" "),
    key=len,
)
# multi-word plants are matched before their parts ("spring onion" before "onion")
_MULTI = [
    "spring onion",
    "leaf salad",
    "sweet pea",
    "broad bean",
    "runner bean",
    "french bean",
    "pak choi",
    "brussels sprout",
    "sweet corn",
    "sweet william",
    "land cress",
    "wild rocket",
    "sweet alyssum",
    "salad mix",
    "lamb's lettuce",
]
_PLANT_RE = re.compile(
    r"\b(" + "|".join(sorted({*_MULTI, *[w for w in PLANTS if w]}, key=len, reverse=True)) + r")\b",
    re.I,
)


def _looks_like_a_title(ln: ocr.TextLine) -> bool:
    text = ln.text.strip()
    return (
        ln.confidence > 0.6
        and 3 <= len(text) <= MAX_NAME_CHARS
        and len(text.split()) <= 5
        and text[0].isalpha()
        and sum(c.isdigit() for c in text) <= 3
        and not NOT_A_NAME.search(text)
    )


def _tidy(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" -:·•|")


def guess_name_and_variety(lines: list[ocr.TextLine]) -> tuple[str | None, str | None]:
    """The plant and variety. A plant from a list of common ones, found in the largest short line
    that starts with it ("Carrot Flyaway F1" gives Carrot and Flyaway F1; "CARROT" over "Maestro F1"
    gives the variety from the next line down). Plants not on the list fall back to the largest
    short line that looks like a title."""
    titles = [ln for ln in lines if _looks_like_a_title(ln)]
    plant_lines = []
    for ln in titles:
        m = _PLANT_RE.search(ln.text)
        if m and m.start() <= 1:  # the line starts with the plant
            plant_lines.append((ln, m))
    if plant_lines:
        ln, m = max(plant_lines, key=lambda t: t[0].height)
        name = m.group(1).title()
        rest = _tidy(ln.text[m.end() :])
        if rest and not NOT_A_NAME.search(rest):
            return name, rest
        below = [
            other
            for other in titles
            if other is not ln
            and 0 < other.y - ln.y < 2.5 * max(ln.height, 1)
            and abs(other.x - ln.x) < 6 * max(ln.height, 1)
            and not _PLANT_RE.fullmatch(other.text.strip())
        ]
        variety = min(below, key=lambda o: o.y - ln.y).text if below else None
        return name, _tidy(variety) if variety else None
    if not titles:
        return None, None
    top = max(titles, key=lambda ln: ln.height)
    return _tidy(top.text).title(), None


def scan(
    image: Image.Image, engine: ocr.OcrEngine | None = None, today: date | None = None
) -> ScanResult:
    """Read one packet photo. ``engine`` defaults to the shared OCR engine."""
    from . import calendar_cv  # needs scipy: only the worker image has it

    engine = engine or ocr.get_engine()
    result = ScanResult()

    graphic = calendar_cv.read_calendar(image)
    if graphic is not None:
        result.calendar = normalise_calendar(graphic.months)
        result.calendar_source = "graphic"
        result.calendar_crop = calendar_cv.crop_bar(image, graphic)
        # the bar is upright, which says which way up the photo is
        rotations = [graphic.rotation, (graphic.rotation + 180) % 360]
    else:
        rotations = [0, 90, 180, 270]

    best = None
    for rotation in rotations:
        turned = image if rotation == 0 else image.rotate(rotation, expand=True)
        lines = engine.read(turned)
        q = ocr.quality(lines)
        if best is None or q > best[0]:
            best = (q, rotation, lines)
    _, result.rotation, lines = best
    result.raw_text = ocr.in_reading_order(lines)
    result.facts = parse_packet_text(result.raw_text, today)
    result.name, result.variety = guess_name_and_variety(lines)

    if result.calendar_source is None and result.facts.calendar_words:
        result.calendar = normalise_calendar(result.facts.calendar_words)
        result.calendar_source = "words"

    result.missing = result.facts.missing()
    if result.name is None:
        result.missing.insert(0, "name")
    if result.calendar_source is None:
        result.missing.append("calendar")
    return result
