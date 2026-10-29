"""Calendar reader tests on drawn calendars: a coloured bar with 12 cells like the packets'."""

import pytest

pytest.importorskip("scipy")

from PIL import Image, ImageDraw  # noqa: E402

from allotment.calendar_cv import crop_bar, read_calendar  # noqa: E402

PINK, BLUE, GREEN, YELLOW = (230, 0, 130), (0, 150, 220), (60, 160, 60), (250, 210, 0)
CELL, HEIGHT = 50, 40


def draw_calendar(
    cells: dict[int, list[tuple]], rotate: int = 0, noise: bool = False
) -> Image.Image:
    """A packet-like image with a framed 12-cell bar. ``cells[m]``: month m's colours, top down."""
    img = Image.new("RGB", (1000, 800), (245, 245, 240))
    d = ImageDraw.Draw(img)
    x0, y0 = 150, 300
    for m in range(1, 13):
        colours = cells.get(m, [])
        left = x0 + (m - 1) * CELL
        for i, colour in enumerate(colours):
            h = HEIGHT // len(colours)
            d.rectangle([left + 2, y0 + i * h, left + CELL - 2, y0 + (i + 1) * h - 1], fill=colour)
    for k in range(13):  # the cell borders and the frame
        x = x0 + k * CELL
        d.line([x, y0 - 4, x, y0 + HEIGHT + 4], fill=(40, 40, 40), width=3 if k in (0, 12) else 2)
    d.line([x0, y0 - 4, x0 + 12 * CELL, y0 - 4], fill=(40, 40, 40), width=3)
    d.line([x0, y0 + HEIGHT + 4, x0 + 12 * CELL, y0 + HEIGHT + 4], fill=(40, 40, 40), width=3)
    for i, c in enumerate(
        (PINK, BLUE, GREEN, YELLOW)
    ):  # the legend: small swatches, not a calendar
        d.rectangle([150 + i * 130, 220, 180 + i * 130, 250], fill=c)
    if noise:
        d.rectangle([0, 0, 1000, 120], fill=(20, 110, 60))  # a dark green banner
    return img.rotate(rotate, expand=True) if rotate else img


CARROT = {  # sow outdoors Mar to Jun, harvest Aug to Dec, nothing in July
    **{m: [BLUE] for m in range(3, 7)},
    **{m: [YELLOW] for m in range(8, 13)},
}
SPLIT = {  # sow on top of harvest in some months, like Suttons' bars
    **{m: [BLUE] for m in (3, 4)},
    **{m: [BLUE, YELLOW] for m in (5, 6)},
    **{m: [YELLOW] for m in (7, 8, 9)},
}


def test_reads_a_simple_calendar():
    read = read_calendar(draw_calendar(CARROT))
    assert read is not None
    assert read.months["sow_outdoors"] == [3, 4, 5, 6]
    assert read.months["harvest"] == [8, 9, 10, 11, 12]
    assert read.months["sow_indoors"] == [] and read.months["plant_out"] == []
    assert read.hits >= 12


def test_a_month_cell_can_hold_two_activities():
    read = read_calendar(draw_calendar(SPLIT))
    assert read.months["sow_outdoors"] == [3, 4, 5, 6]
    assert read.months["harvest"] == [5, 6, 7, 8, 9]


def test_all_four_activities():
    cells = {
        2: [PINK],
        3: [PINK, BLUE],
        4: [PINK, BLUE],
        5: [GREEN, BLUE],
        6: [GREEN, YELLOW],
        7: [YELLOW],
        8: [YELLOW],
    }
    months = read_calendar(draw_calendar(cells)).months
    assert months == {
        "sow_indoors": [2, 3, 4],
        "sow_outdoors": [3, 4, 5],
        "plant_out": [5, 6],
        "harvest": [6, 7, 8],
    }


@pytest.mark.parametrize("turn", [90, 270])
def test_a_packet_photographed_sideways_is_turned_the_right_way(turn):
    read = read_calendar(draw_calendar(SPLIT, rotate=turn))
    assert read.months["sow_outdoors"] == [3, 4, 5, 6]
    assert read.months["harvest"] == [5, 6, 7, 8, 9]


def test_upside_down_is_corrected_by_the_stripe_order():
    read = read_calendar(draw_calendar(SPLIT, rotate=180))
    assert read.months["sow_outdoors"] == [3, 4, 5, 6]
    assert read.upright_vote > 0


def test_a_big_green_banner_is_not_a_calendar():
    read = read_calendar(draw_calendar(CARROT, noise=True))
    assert read.months["sow_outdoors"] == [3, 4, 5, 6]
    assert read.months["plant_out"] == []


def test_legend_swatches_alone_are_not_a_calendar():
    blank = draw_calendar({})
    assert read_calendar(blank) is None


def test_no_graphic_at_all():
    assert read_calendar(Image.new("RGB", (800, 600), (240, 240, 235))) is None


def test_the_crop_for_the_review_screen_shows_the_bar():
    img = draw_calendar(CARROT)
    read = read_calendar(img)
    crop = crop_bar(img, read)
    assert crop.width > crop.height > 40
