"""Reads the colour-bar sowing calendar on the back of a seed packet, from pixels alone.

No model: segment the four palette colours, find the bar, find its 13 vertical grid lines from the
dark valleys in the colour band, then see which colours fill each of the 12 month columns. Worked
out and measured in docs/seed-scanning-spike.md (99.7% of month-cells on 20 real packets).

Colours mean the same on the packets seen so far: pink or coral sow indoors, blue sow outdoors,
green plant out, yellow harvest (or flowers). Inside a month cell the stripes always run pink,
green, blue, yellow from the top, which also tells which way up the photo is.

Needs numpy, scipy and Pillow (the worker image has them).
"""

from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ACTIVITY = {
    "pink": "sow_indoors",
    "blue": "sow_outdoors",
    "green": "plant_out",
    "yellow": "harvest",
}
# PIL HSV scale (0 to 255): hue range, minimum saturation, minimum value. Pink wraps past 255.
CLASSES = {
    "blue": ((120, 150), 130, 130),
    "yellow": ((22, 44), 150, 170),
    "pink": ((222, 264), 110, 140),
    "green": ((68, 105), 100, 130),
}
STRIPE_ORDER = {"pink": 0, "green": 1, "blue": 2, "yellow": 3}
LONG_SIDE = 1600
MIN_HITS = 11  # of 13 grid lines
CELL_COVER = 0.06  # share of a month cell a colour must fill to count


@dataclass
class CalendarRead:
    """What was found. ``rotation`` is the counter-clockwise turn that made the bar horizontal."""

    months: dict[str, list[int]]
    rotation: int
    hits: int  # grid lines matched, of 13
    upright_vote: int  # > 0: stripes run the right way up; < 0: the photo is upside down
    box: tuple[int, int, int, int]  # x0, y0, x1, y1 of the bar in the rotated, resized image
    size: tuple[int, int]  # that image's width and height
    cover: list[dict[str, float]] = field(default_factory=list)


def _resize(image: Image.Image, rotation: int) -> Image.Image:
    im = image.convert("RGB")
    if rotation:
        im = im.rotate(rotation, expand=True)
    scale = LONG_SIDE / max(im.size)
    return im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)


def _masks(im: Image.Image, loose: bool = False) -> dict[str, np.ndarray]:
    hsv = np.asarray(im.convert("HSV")).astype(np.int16)
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    out = {}
    for name, ((lo, hi), min_s, min_v) in CLASSES.items():
        if loose:
            min_s, min_v = int(min_s * 0.6), int(min_v * 0.8)
        h = np.where(hue < 16, hue + 256, hue) if hi >= 256 else hue
        m = (h >= lo) & (h <= hi) & (sat >= min_s) & (val >= min_v)
        m = ndi.binary_opening(m, structure=np.ones((3, 3)))
        labels, _ = ndi.label(m)
        for i, sl in enumerate(ndi.find_objects(labels), 1):  # banners and photos are big blobs
            if sl[0].stop - sl[0].start > 95:
                m[sl][labels[sl] == i] = False
        out[name] = m
    return out


def _candidates(masks: dict[str, np.ndarray], reach: int) -> list[tuple[slice, slice]]:
    """Clusters of palette colour much wider than tall, widest first."""
    union = np.zeros_like(next(iter(masks.values())))
    for m in masks.values():
        union |= m
    labels, _ = ndi.label(ndi.binary_dilation(union, structure=np.ones((3, reach))))
    found = []
    for sl in ndi.find_objects(labels):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        kinds = sum(1 for m in masks.values() if m[sl].any())
        if w >= 90 and w / h >= 2.5 and kinds >= 2:
            found.append((w * kinds, sl))
    return [sl for _, sl in sorted(found, key=lambda t: -t[0])[:6]]


def _valleys(lum: np.ndarray, win: int = 21, thr: float = 10) -> list[tuple[float, float]]:
    pad = win // 2
    med = ndi.median_filter(np.pad(lum, pad, mode="edge"), size=win)[pad:-pad]
    dip = med - lum
    cols = np.where(dip > thr)[0]
    if len(cols) == 0:
        return []
    groups = np.split(cols, np.where(np.diff(cols) > 2)[0] + 1)
    return [(float(np.average(g, weights=dip[g])), float(dip[g].max())) for g in groups]


def _fit_grid(peaks: list[tuple[float, float]], x0: int, x1: int):
    """13 equally spaced lines (12 cells) that match the valleys and span the colour.

    The bar's outer frame lines are the strongest, so ending on strong lines beats a fit shifted by
    a column, and strong lines continuing past either end mean the bar goes on.
    """
    pos = np.array([p for p, _ in peaks])
    depth = np.array([d for _, d in peaks])
    median = np.median(depth)
    best = None
    for anchor in pos:
        for pitch in np.arange(14, 140, 0.5):
            for shift in range(-12, 1):
                start = anchor + shift * pitch
                lines = start + pitch * np.arange(13)
                if lines[0] - 0.4 * pitch > x0 or lines[-1] + 0.4 * pitch < x1:
                    continue
                near = [
                    int(np.argmin(abs(pos - ln))) if abs(pos - ln).min() < 0.15 * pitch else -1
                    for ln in lines
                ]
                hits = sum(i >= 0 for i in near)
                ends = sum(depth[near[k]] / median for k in (0, 12) if near[k] >= 0)
                overhang = 0
                for ln in (lines[0] - pitch, lines[-1] + pitch):
                    close = abs(pos - ln) < 0.15 * pitch
                    if close.any() and depth[close].max() > 0.6 * median:
                        overhang += 1
                score = hits + 0.4 * min(ends, 3) - 0.8 * overhang - 0.002 * pitch
                if best is None or score > best[0]:
                    edges = [
                        float(pos[i]) if i >= 0 else float(ln)
                        for i, ln in zip(near, lines, strict=True)
                    ]
                    best = (score, pitch, hits, edges)
    return best


def _upright_vote(loose, edges, pitch, y0, y1) -> int:
    """Month cells whose stripes run pink, green, blue, yellow from the top, minus the rest."""
    vote = 0
    for c in range(12):
        x0, x1 = int(edges[c] + 0.2 * pitch), int(edges[c + 1] - 0.2 * pitch)
        mids = {}
        for name, m in loose.items():
            ys, _ = np.where(m[y0:y1, max(x0, 0) : x1])
            if len(ys) > CELL_COVER * (y1 - y0) * max(x1 - x0, 1):
                mids[name] = ys.mean()
        for a in mids:
            for b in mids:
                if STRIPE_ORDER[a] < STRIPE_ORDER[b] and abs(mids[a] - mids[b]) > 3:
                    vote += 1 if mids[a] < mids[b] else -1
    return vote


def _read_at(image: Image.Image, rotation: int) -> tuple[float, CalendarRead] | None:
    im = _resize(image, rotation)
    masks, loose = _masks(im), _masks(im, loose=True)
    union = np.zeros(im.size[::-1], bool)
    for m in masks.values():
        union |= m
    lum = np.asarray(im.convert("L")).astype(np.float32)
    best, seen = None, set()
    for sl in [*_candidates(masks, 9), *_candidates(masks, 91)]:
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        ys, xs = np.where(union[y0:y1, x0:x1])
        if len(xs) == 0:
            continue
        # a calendar's colour is nearly continuous across it; legend swatches are small and spaced
        if len(np.unique(xs)) / (xs.max() - xs.min() + 1) < 0.6:
            continue
        y0, y1, x0, x1 = y0 + ys.min(), y0 + ys.max() + 1, x0 + xs.min(), x0 + xs.max() + 1
        key = (x0 // 8, y0 // 8, x1 // 8, y1 // 8)
        if key in seen:
            continue
        seen.add(key)
        peaks = _valleys(lum[y0:y1].mean(axis=0))
        if len(peaks) < 5:
            continue
        fit = _fit_grid(peaks, x0, x1)
        if fit is None:
            continue
        labels, _ = ndi.label(union[y0:y1, x0:x1])
        widest = max(s[1].stop - s[1].start for s in ndi.find_objects(labels))
        if widest < 0.8 * fit[1]:
            continue
        if best is None or fit[0] > best[0][0]:
            best = (fit, (x0, y0, x1, y1))
    if best is None or best[0][2] < MIN_HITS:
        return None
    (score, pitch, hits, edges), (x0, y0, x1, y1) = best
    months: dict[str, list[int]] = {a: [] for a in ACTIVITY.values()}
    cover = []
    for c in range(12):
        cx0, cx1 = int(edges[c] + 0.2 * pitch), int(edges[c + 1] - 0.2 * pitch)
        share = {}
        for name, m in loose.items():
            region = m[y0:y1, max(cx0, 0) : cx1]
            share[name] = float(region.mean()) if region.size else 0.0
            if share[name] > CELL_COVER:
                months[ACTIVITY[name]].append(c + 1)
        cover.append(share)
    read = CalendarRead(
        months=months,
        rotation=rotation,
        hits=hits,
        upright_vote=_upright_vote(loose, edges, pitch, y0, y1),
        box=(int(x0), int(y0), int(x1), int(y1)),
        size=im.size,
        cover=cover,
    )
    return score, read


def read_calendar(image: Image.Image) -> CalendarRead | None:
    """The calendar on a packet photo, or None if there is no colour-bar graphic.

    Tries the four quarter turns. The turn whose grid fits best wins; where a turn and its opposite
    fit equally (the bar looks the same upside down) the stripe order decides, so the months come
    out left to right as January to December.
    """
    reads = [r for rot in (0, 90, 180, 270) if (r := _read_at(image, rot))]
    if not reads:
        return None
    top = max(score for score, _ in reads)
    close = [r for score, r in reads if score >= top - 0.5]
    return max(close, key=lambda r: (r.upright_vote > 0, r.upright_vote, r.hits))


def crop_bar(image: Image.Image, read: CalendarRead, margin: int = 40) -> Image.Image:
    """The part of the photo showing the calendar, upright, for the review screen."""
    im = _resize(image, read.rotation)
    x0, y0, x1, y1 = read.box
    return im.crop(
        (
            max(x0 - margin, 0),
            max(y0 - margin, 0),
            min(x1 + margin, im.width),
            min(y1 + margin, im.height),
        )
    )
