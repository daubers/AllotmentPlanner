from datetime import date

import pytest

from allotment.packet_text import (
    find_depth_mm,
    find_germination_days,
    find_seed_count,
    find_sow_by_year,
    find_supplier,
    months_from_words,
    months_in,
    parse_packet_text,
)

TODAY = date(2026, 10, 29)

# Text as printed on real packets (see docs/seed-scanning-spike.md).
FOTHERGILLS_CARROT = """Carrot Flyaway F1
Sow outdoors thinly where they are to crop, 1.5cm (1/2") deep directly into finely prepared soil
which has already been watered. Allow 30cm (1') between rows.
Seedlings usually appear in 14-21 days.
Mr. Fothergill's Seeds, Kentford, Newmarket
Packed in year ending OCT 2024
Sow by DEC 2028"""

JOHNSONS_CORIANDER = """Average 150 seeds
CORIANDER Filtro
For outdoor sowing
When March to June
Where In the growing position
How Sow thinly, cover with fine soil
Seedlings appear 14-21 days
Harvest May to November, pick the leaves as required
For indoor sowing
When All year round for pots indoors
Harvest All year round, pick the leaves as required
Sow by DEC 2027 B"""


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ('Sow 1.5cm (1/2") deep directly into soil', 15),
        ('Sow thinly direct into soil at a depth of 13mm (1/2").', 13),
        ("Sow outdoors 5cm deep in flat drills", 50),
        ('Sow seeds in a well-drained soil 13mm (1/2") deep in a lightly-shaded site', 13),
        ('Sow 0.5cm (1/4") deep, thinly in small pots', 5),
        ("Sow thinly into pots covering seed lightly", None),
        ("Allow 30cm (1') between rows", None),
        ("Sow 9999cm deep", None),
    ],
)
def test_depth(text, want):
    assert find_depth_mm(text) == want


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("Seedlings usually appear in 14-21 days.", (14, 21)),
        ("Germination 15-20 days. Pull small for salad use", (15, 20)),
        ("Seedlings usually appear in 10–18 days", (10, 18)),
        ("Seedlings appear 14-28 days", (14, 28)),
        ("Seedlings appear in 7 to 14 days", (7, 14)),
        ("Seedlings appear in about 10 days", (10, 10)),
        ("Harvest in 8 weeks", None),
        ("Sow 14-21 days before the last frost", None),
    ],
)
def test_germination(text, want):
    assert find_germination_days(text) == want


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("Packed in year ending OCT 2024\nSow by DEC 2028", 2028),
        ("Sow by\nDEC 2027 B", 2027),
        ("SOW BY YE 2028\nPKD YE 2025", 2028),
        ("Sow by: 7/2024", 2024),
        ("Best before end 2027", 2027),
        ("Sow by 2099", None),
        ("Packed in year ending OCT 2024", None),
    ],
)
def test_sow_by_year(text, want):
    assert find_sow_by_year(text, TODAY) == want


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("Average 500 seeds", 500),
        ("Average Contents 70 Seeds", 70),
        ("Average 1,500 seeds", 1500),
        ("250 seeds", 250),
        ("Sow seeds thinly", None),
    ],
)
def test_seed_count(text, want):
    assert find_seed_count(text) == want


def test_supplier():
    assert find_supplier("Mr. Fothergill’s Seeds, Kentford") == "Mr Fothergill's"
    assert find_supplier("SUTTONS SEEDS PAIGNTON, ENGLAND") == "Suttons"
    assert find_supplier("www.johnsons-seeds.com") == "Johnsons"
    assert find_supplier("Some other company") is None


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("March to June", [3, 4, 5, 6]),
        ("In growing position, May to November", [5, 6, 7, 8, 9, 10, 11]),
        ("Nov to Feb", [1, 2, 11, 12]),
        ("All year round for pots indoors", list(range(1, 13))),
        ("June onwards", list(range(6, 13))),
        ("March, May", [3, 5]),
        ("Mayhem and marching", []),
    ],
)
def test_months_in(text, want):
    assert months_in(text) == want


def test_calendar_from_words_for_a_packet_with_no_graphic():
    assert months_from_words(JOHNSONS_CORIANDER) == {
        "sow_outdoors": [3, 4, 5, 6],
        "sow_indoors": list(range(1, 13)),
        "harvest": list(range(1, 13)),
    }


def test_a_whole_packet():
    facts = parse_packet_text(FOTHERGILLS_CARROT, TODAY)
    assert (facts.supplier, facts.sow_depth_mm, facts.best_before_year) == (
        "Mr Fothergill's",
        15,
        2028,
    )
    assert (facts.germinate_days_min, facts.germinate_days_max) == (14, 21)
    assert facts.seeds_in_packet is None
    assert facts.missing() == ["seeds_in_packet"]


def test_an_empty_read_finds_nothing_and_says_so():
    facts = parse_packet_text("", TODAY)
    assert facts.missing() == [
        "supplier",
        "seeds_in_packet",
        "sow_depth_mm",
        "best_before_year",
        "germinate_days",
    ]
    assert facts.calendar_words == {}
