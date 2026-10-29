from datetime import date

import pytest

from allotment.ocr import TextLine, in_reading_order, quality
from allotment.packet_scan import guess_name_and_variety


def line(text, x=100, y=100, h=30, c=0.95):
    return TextLine(text, c, x, y, h)


def test_name_and_variety_in_one_line():
    lines = [
        line("Carrot Flyaway F1", h=44),
        line("Sow outdoors thinly where they are to crop", y=300),
    ]
    assert guess_name_and_variety(lines) == ("Carrot", "Flyaway F1")


def test_variety_on_the_line_below_and_the_brand_ignored():
    lines = [
        line("SUTTONS", x=40, y=60, h=70),
        line("CARROT", x=300, y=100, h=52),
        line("Maestro F1", x=300, y=160, h=30),
        line("Resistant to carrot fly attack", x=300, y=260),
    ]
    assert guess_name_and_variety(lines) == ("Carrot", "Maestro F1")


def test_a_plain_plant_with_no_variety():
    lines = [
        line("SUTTONS", h=60),
        line("BORAGE", y=210, h=40),
        line("Average Contents 70 Seeds", y=40),
    ]
    assert guess_name_and_variety(lines) == ("Borage", None)


def test_two_word_plants_win_over_their_parts():
    lines = [line("SPRING ONION", h=40), line("Marksman", y=150, h=28)]
    assert guess_name_and_variety(lines) == ("Spring Onion", "Marksman")


def test_a_plant_not_on_the_list_falls_back_to_the_biggest_title():
    lines = [line("Salsify Mammoth", h=50), line("www.example.co.uk", y=400, h=60)]
    assert guess_name_and_variety(lines) == ("Salsify Mammoth", None)


def test_sentences_and_low_confidence_are_not_names():
    lines = [
        line("Sow thinly where they are to crop and water well", h=60),
        line("Carrot", h=50, c=0.3),
    ]
    assert guess_name_and_variety(lines) == (None, None)
    assert guess_name_and_variety([]) == (None, None)


def test_reading_order_and_quality():
    lines = [line("world", x=200, y=10), line("hello", x=20, y=12), line("next row", x=20, y=90)]
    assert in_reading_order(lines) == "hello world\nnext row"
    assert quality([line("abcdef", c=0.9), line("noise", c=0.2)]) == pytest.approx(5.4)


# --- the whole scan, with a fake OCR engine and a drawn calendar ---------------------------------

TEXT = [
    line("Carrot Flyaway F1", h=44),
    line("Average 500 seeds", y=20),
    line("Sow outdoors thinly where they are to crop, 1.5cm (1/2) deep directly into soil", y=300),
    line("Seedlings usually appear in 14-21 days.", y=340),
    line("Mr. Fothergill's Seeds, Kentford", y=800),
    line("Packed in year ending OCT 2024", y=830),
    line("Sow by DEC 2028", y=860),
]


class FakeEngine:
    def __init__(self, lines):
        self.lines = lines
        self.seen = 0

    def read(self, image):
        self.seen += 1
        return self.lines


def test_a_whole_scan_with_a_calendar_graphic():
    pytest.importorskip("scipy")
    from allotment.packet_scan import scan

    from .test_calendar_cv import CARROT, draw_calendar

    result = scan(draw_calendar(CARROT), FakeEngine(TEXT), today=date(2026, 10, 29))
    assert (result.name, result.variety) == ("Carrot", "Flyaway F1")
    assert result.calendar_source == "graphic"
    assert result.calendar["sow_outdoors"] == [3, 4, 5, 6]
    assert result.calendar["harvest"] == [8, 9, 10, 11, 12]
    assert result.calendar_crop is not None
    f = result.facts
    assert (f.supplier, f.sow_depth_mm, f.best_before_year, f.seeds_in_packet) == (
        "Mr Fothergill's",
        15,
        2028,
        500,
    )
    assert (f.germinate_days_min, f.germinate_days_max) == (14, 21)
    assert result.missing == []


def test_a_packet_with_no_graphic_takes_its_calendar_from_the_words():
    pytest.importorskip("scipy")
    from PIL import Image

    from allotment.packet_scan import scan

    words = [
        line("CORIANDER Filtro", h=44),
        line("For outdoor sowing", y=200),
        line("When March to June", y=240),
        line("Harvest May to November", y=280),
        line("Sow by DEC 2027", y=900),
    ]
    engine = FakeEngine(words)
    result = scan(Image.new("RGB", (600, 800), (240, 240, 235)), engine, today=date(2026, 10, 29))
    assert engine.seen == 4  # no calendar to say which way up, so all four turns were read
    assert result.calendar_source == "words"
    assert result.calendar["sow_outdoors"] == [3, 4, 5, 6]
    assert result.calendar["harvest"] == [5, 6, 7, 8, 9, 10, 11]
    assert "calendar" not in result.missing and "sow_depth_mm" in result.missing


def test_a_blank_photo_says_what_it_could_not_find():
    pytest.importorskip("scipy")
    from PIL import Image

    from allotment.packet_scan import scan

    result = scan(Image.new("RGB", (400, 400), (250, 250, 250)), FakeEngine([]))
    assert result.name is None and result.calendar_source is None
    assert result.missing[0] == "name" and "calendar" in result.missing
