"""A built-in list of common crops, so a plan can use crops you have no seed packet for yet.

Pure data, no database. Values are typical for the UK and are only starting points: a seed
packet's own figures (spacing, days to maturity, months) win when a plan item is linked to one.
Months are 1 to 12 and the tuples have the same shape as a packet's ``calendar``; a window may
wrap the new year (10, 11, 2, 3).
"""

from dataclasses import asdict, dataclass
from datetime import date

METHODS = ("direct_sow", "transplant")


@dataclass(frozen=True)
class Crop:
    key: str
    name: str
    family: str  # botanical family, kept for rotation hints later
    category: str
    method_default: str  # direct_sow, or transplant (sown in a tray, then planted out)
    spacing_plant_cm: int
    spacing_row_cm: int
    germinate_days: int
    maturity_days_min: int  # sowing to first harvest
    maturity_days_max: int
    sow_depth_mm: int
    sow_months: tuple[int, ...]  # when to sow (indoors for a transplant crop)
    plant_out_months: tuple[int, ...]  # only for transplant crops
    harvest_months: tuple[int, ...]
    succession_days: int | None = None  # gap between repeat sowings; None = not usually repeated
    notes: str = ""


def _span(start: int, end: int) -> tuple[int, ...]:
    """The months from start to end inclusive, wrapping the year (10 to 2 is Oct to Feb)."""
    months, m = [], start
    while True:
        months.append(m)
        if m == end:
            return tuple(months)
        m = m % 12 + 1


def _crop(
    key, name, family, category, method, plant, row, germ, mat, depth, sow, out, harvest, **kw
):
    return Crop(
        key,
        name,
        family,
        category,
        method,
        plant,
        row,
        germ,
        mat[0],
        mat[1],
        depth,
        sow,
        out,
        harvest,
        **kw,
    )


D, T = "direct_sow", "transplant"
NONE: tuple[int, ...] = ()

# fmt: off
_CROPS = [
    _crop("lettuce", "Lettuce", "Asteraceae", "salad", D, 30, 30, 7, (50, 70), 10,
        _span(3, 8), NONE, _span(5, 10),
        succession_days=14),
    _crop("rocket", "Rocket", "Brassicaceae", "salad", D, 10, 15, 5, (30, 50), 10,
        _span(3, 9), NONE, _span(4, 10),
        succession_days=14),
    _crop("radish", "Radish", "Brassicaceae", "root", D, 3, 15, 5, (21, 35), 10,
        _span(3, 9), NONE, _span(4, 10),
        succession_days=10),
    _crop("spring_onion", "Spring onion", "Amaryllidaceae", "allium", D, 3, 15, 10, (60, 80), 10,
        _span(3, 8), NONE, _span(5, 10),
        succession_days=21),
    _crop("spinach", "Spinach", "Amaranthaceae", "leaf", D, 10, 30, 10, (40, 60), 20,
        (3, 4, 5, 8, 9), NONE, _span(5, 11),
        succession_days=21, notes="Bolts in summer heat; sow spring and late summer."),
    _crop("chard", "Chard", "Amaranthaceae", "leaf", D, 30, 40, 10, (55, 75), 20,
        _span(4, 7), NONE, _span(6, 11)),
    _crop("beetroot", "Beetroot", "Amaranthaceae", "root", D, 10, 30, 10, (60, 90), 20,
        _span(4, 7), NONE, _span(6, 10),
        succession_days=21),
    _crop("carrot", "Carrot", "Apiaceae", "root", D, 5, 25, 14, (80, 120), 10,
        _span(3, 7), NONE, _span(6, 11),
        succession_days=21),
    _crop("parsnip", "Parsnip", "Apiaceae", "root", D, 15, 30, 21, (150, 200), 15,
        _span(3, 5), NONE, _span(10, 2)),
    _crop("turnip", "Turnip", "Brassicaceae", "root", D, 10, 25, 7, (45, 70), 15,
        _span(3, 8), NONE, _span(5, 11),
        succession_days=21),
    _crop("onion_sets", "Onion (sets)", "Amaryllidaceae", "allium", D, 10, 25, 0, (100, 140), 25,
        _span(3, 4), NONE, _span(7, 9),
        notes="Planted as small bulbs, so there is no germination."),
    _crop("garlic", "Garlic", "Amaryllidaceae", "allium", D, 15, 30, 0, (200, 250), 25,
        (10, 11, 2, 3), NONE, _span(6, 8),
        notes="Planted as cloves in autumn (or early spring)."),
    _crop("leek", "Leek", "Amaryllidaceae", "allium", T, 15, 30, 14, (150, 210), 12,
        _span(2, 4), _span(5, 7), _span(10, 3)),
    _crop("potato_first_early", "Potato (first early)", "Solanaceae", "root", D, 30, 60, 0,
        (90, 110), 100,
        _span(3, 4), NONE, _span(6, 7),
        notes="Planted as seed tubers."),
    _crop("potato_maincrop", "Potato (maincrop)", "Solanaceae", "root", D, 40, 75, 0,
        (130, 160), 100,
        _span(4, 5), NONE, _span(8, 10),
        notes="Planted as seed tubers."),
    _crop("broad_bean", "Broad bean", "Fabaceae", "legume", D, 20, 45, 14, (90, 120), 50,
        (2, 3, 4, 10, 11), NONE, _span(6, 8)),
    _crop("runner_bean", "Runner bean", "Fabaceae", "legume", D, 15, 60, 10, (90, 120), 40,
        _span(5, 6), NONE, _span(7, 10),
        notes="Needs a wigwam or rows of canes."),
    _crop("french_bean", "French bean", "Fabaceae", "legume", D, 10, 40, 10, (55, 80), 40,
        _span(5, 7), NONE, _span(7, 10),
        succession_days=21),
    _crop("pea", "Pea", "Fabaceae", "legume", D, 5, 60, 10, (80, 100), 40,
        _span(3, 6), NONE, _span(6, 9),
        succession_days=14),
    _crop("courgette", "Courgette", "Cucurbitaceae", "fruiting", T, 90, 90, 7, (70, 90), 20,
        _span(4, 5), _span(5, 6), _span(7, 10)),
    _crop("squash", "Squash / pumpkin", "Cucurbitaceae", "fruiting", T, 100, 100, 7, (100, 140), 20,
        _span(4, 5), _span(5, 6), _span(9, 10)),
    _crop("sweetcorn", "Sweetcorn", "Poaceae", "fruiting", T, 35, 35, 8, (90, 110), 25,
        _span(4, 5), _span(5, 6), _span(8, 10),
        notes="Plant in a block, not a single row, for pollination."),
    _crop("tomato", "Tomato", "Solanaceae", "fruiting", T, 45, 60, 8, (100, 130), 6,
        _span(2, 4), _span(5, 6), _span(7, 10)),
    _crop("cucumber", "Cucumber", "Cucurbitaceae", "fruiting", T, 45, 90, 7, (70, 90), 15,
        _span(4, 5), _span(5, 6), _span(7, 9)),
    _crop("kale", "Kale", "Brassicaceae", "brassica", T, 45, 45, 7, (100, 150), 12,
        _span(4, 6), _span(6, 7), _span(10, 3)),
    _crop("cabbage", "Cabbage", "Brassicaceae", "brassica", T, 45, 45, 7, (90, 150), 12,
        _span(3, 5), _span(5, 7), _span(7, 12)),
    _crop("cauliflower", "Cauliflower", "Brassicaceae", "brassica", T, 60, 60, 7, (100, 160), 12,
        _span(3, 5), _span(5, 6), _span(7, 11)),
    _crop("broccoli", "Broccoli", "Brassicaceae", "brassica", T, 45, 45, 7, (80, 120), 12,
        _span(3, 5), _span(5, 6), _span(6, 10)),
    _crop("brussels_sprouts", "Brussels sprouts", "Brassicaceae", "brassica", T, 60, 60, 7,
        (180, 250), 12,
        _span(3, 4), _span(5, 6), _span(10, 3)),
    _crop("celeriac", "Celeriac", "Apiaceae", "root", T, 30, 30, 14, (150, 200), 3,
        _span(3, 4), _span(5, 6), _span(10, 12)),
    _crop("coriander", "Coriander", "Apiaceae", "herb", D, 10, 20, 10, (30, 50), 10,
        _span(4, 8), NONE, _span(5, 10),
        succession_days=14),
    _crop("parsley", "Parsley", "Apiaceae", "herb", D, 20, 25, 21, (70, 90), 10,
        _span(3, 7), NONE, _span(6, 11)),
    _crop("dill", "Dill", "Apiaceae", "herb", D, 20, 25, 10, (40, 60), 10,
        _span(4, 7), NONE, _span(6, 9),
        succession_days=21),
    _crop("basil", "Basil", "Lamiaceae", "herb", T, 20, 20, 7, (50, 70), 5,
        _span(4, 6), _span(6, 7), _span(6, 9)),
    _crop("sweet_pea", "Sweet pea", "Fabaceae", "flower", T, 15, 30, 14, (100, 140), 12,
        (10, 11, 2, 3, 4), _span(4, 5), _span(6, 8)),
]
# fmt: on

CROPS: dict[str, Crop] = {c.key: c for c in _CROPS}


def get_crop(key: str | None) -> Crop | None:
    return CROPS.get(key) if key else None


def search(q: str | None = None) -> list[Crop]:
    """Crops whose name, key or family contains ``q`` (any case); every crop, by name, if empty."""
    needle = (q or "").strip().lower()
    found = [
        c
        for c in CROPS.values()
        if not needle or needle in c.name.lower() or needle in c.key or needle in c.family.lower()
    ]
    return sorted(found, key=lambda c: c.name.lower())


def to_dict(crop: Crop) -> dict:
    out = asdict(crop)
    for key in ("sow_months", "plant_out_months", "harvest_months"):
        out[key] = list(out[key])
    return out


def next_in_window(months: tuple[int, ...] | list[int], on: date) -> date | None:
    """The first day on or after ``on`` that falls in one of ``months`` (the year may roll over).

    ``on`` itself if its month is in the window; otherwise the 1st of the next month that is.
    None when there are no months at all.
    """
    if not months:
        return None
    wanted = set(months)
    year, month = on.year, on.month
    if month in wanted:
        return on
    for _ in range(12):
        month = month % 12 + 1
        year += month == 1
        if month in wanted:
            return date(year, month, 1)
    return None
