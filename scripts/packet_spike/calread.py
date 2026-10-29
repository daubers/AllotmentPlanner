"""Prototype: read a packet's colour-bar calendar from pixels. No OCR, no model."""
import json, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ACT = {"pink": "sow_indoors", "blue": "sow_outdoors", "green": "plant_out", "yellow": "harvest"}
# PIL HSV scale (0-255): hue range, min saturation, min value
CLASSES = {
    "blue": ((120, 150), 120, 100),
    "yellow": ((22, 44), 130, 140),
    "pink": ((222, 264), 90, 120),   # magenta (~240) and coral (~252); wraps past 255 to red (0-8)
    "green": ((68, 105), 100, 130),
}

def load(path, rot, long_side=1600):
    im = Image.open(path).convert("RGB")
    if rot: im = im.rotate(rot, expand=True)   # counter-clockwise degrees
    s = long_side / max(im.size)
    return im.resize((round(im.width*s), round(im.height*s)), Image.LANCZOS)

def class_masks(im, loose=False):
    h = np.asarray(im.convert("HSV")).astype(np.int16)
    H, S, V = h[..., 0], h[..., 1], h[..., 2]
    out = {}
    for k, ((lo, hi), s, v) in CLASSES.items():
        if loose: s, v = int(s * 0.6), int(v * 0.8)
        Hh = H % 256 if hi < 256 else np.where(H < 16, H + 256, H)
        m = (Hh >= lo) & (Hh <= hi) & (S >= s) & (V >= v)
        m = ndi.binary_opening(m, structure=np.ones((3, 3)))
        # banners and photos are big blobs; calendar cells and stripes are small
        lab, n = ndi.label(m)
        for i, sl in enumerate(ndi.find_objects(lab), 1):
            if sl[0].stop - sl[0].start > 95: m[sl][lab[sl] == i] = False
        out[k] = m
    return out

def find_bars(masks, reach=91):
    """Clusters of palette colour that are much wider than tall, widest first."""
    names = list(masks)
    u = np.zeros_like(next(iter(masks.values())))
    for m in masks.values(): u |= m
    d = ndi.binary_dilation(u, structure=np.ones((3, reach)))   # reach: joins stretches across an empty month
    lab, n = ndi.label(d)
    out = []
    for i, sl in enumerate(ndi.find_objects(lab), 1):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        kinds = sum(1 for k in names if masks[k][sl].any())
        if w < 90 or w / h < 2.5 or kinds < 2: continue
        out.append((w * kinds, sl))
    return [sl for _, sl in sorted(out, key=lambda t: -t[0])[:6]]

def valleys(lum, win=21, thr=10):
    pad = win // 2
    ext = np.pad(lum, pad, mode="edge")
    med = ndi.median_filter(ext, size=win)[pad:-pad]
    dip = med - lum
    cols = np.where(dip > thr)[0]
    if len(cols) == 0: return []
    groups = np.split(cols, np.where(np.diff(cols) > 2)[0] + 1)
    return [(float(np.average(g, weights=dip[g])), float(dip[g].max())) for g in groups]

def fit_grid(peaks, x0, x1):
    """13 equally spaced lines (12 cells) matching the valleys, spanning the colour.
    The outer frame lines are the strongest, so ending on strong lines beats a shifted fit."""
    pos = np.array([q for q, _ in peaks]); depth = np.array([d for _, d in peaks])
    med = np.median(depth)
    best = None
    for a in pos:
        for p in np.arange(14, 140, 0.5):
            for shift in range(-12, 1):
                start = a + shift * p
                lines = start + p * np.arange(13)
                if lines[0] - 0.4 * p > x0 or lines[-1] + 0.4 * p < x1: continue
                idx = [int(np.argmin(abs(pos - l))) if abs(pos - l).min() < 0.15 * p else -1 for l in lines]
                hit = sum(i >= 0 for i in idx)
                ends = sum(depth[idx[k]] / med for k in (0, 12) if idx[k] >= 0)
                over = 0
                for l in (lines[0] - p, lines[-1] + p):  # strong lines beyond the ends mean the bar goes on
                    near = abs(pos - l) < 0.15 * p
                    if near.any() and depth[near].max() > 0.6 * med: over += 1
                score = hit + 0.4 * min(ends, 3) - 0.8 * over - 0.002 * p
                if best is None or score > best[0]: best = (score, start, p, hit, [float(pos[i]) if i >= 0 else float(l) for i, l in zip(idx, lines)])
    return best

def read(path, rot):
  try:
    return _read(path, rot)
  except Exception as e:  # noqa
    return {"ok": False, "why": repr(e)}

def _read(path, rot):
    im = load(path, rot)
    masks = class_masks(im)
    loose = class_masks(im, loose=True)
    u = np.zeros(im.size[::-1], bool)
    for m in masks.values(): u |= m
    lum_all = np.asarray(im.convert("L")).astype(np.float32)
    best = None
    seen = set()
    cands = [sl for reach in (9, 91) for sl in find_bars(masks, reach)]
    for sl in cands:
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        ys, xs = np.where(u[y0:y1, x0:x1])
        if len(xs) == 0: continue
        if u[y0:y1, x0:x1].any(axis=0).mean() < 0.6 and len(np.unique(xs)) / (xs.max() - xs.min() + 1) < 0.6: continue
        y0, y1, x0, x1 = y0 + ys.min(), y0 + ys.max() + 1, x0 + xs.min(), x0 + xs.max() + 1
        pk = valleys(lum_all[y0:y1].mean(axis=0))
        if len(pk) < 5: continue
        key = (x0 // 8, y0 // 8, x1 // 8, y1 // 8)
        if key in seen: continue
        seen.add(key)
        fit = fit_grid(pk, x0, x1)
        if fit is None: continue
        # colour blocks narrower than a month column are legend swatches, not a calendar
        lab, _ = ndi.label(u[y0:y1, x0:x1])
        widest = max(sl_[1].stop - sl_[1].start for sl_ in ndi.find_objects(lab))
        if widest < 0.8 * fit[2]: continue
        if best is None or fit[0] > best[0][0]: best = (fit, (x0, y0, x1, y1))
    if best is None or best[0][3] < 11: return {"ok": False, "why": "no grid", "hits": None if best is None else best[0][3]}
    (_, start, p, hit, edges), (x0, y0, x1, y1) = best
    months = {a: [] for a in ACT.values()}
    cover = []
    for c in range(12):
        cx0, cx1 = int(edges[c] + 0.2 * p), int(edges[c + 1] - 0.2 * p)
        cov = {}
        for k, m in loose.items():
            region = m[y0:y1, max(cx0, 0):cx1]
            cov[k] = float(region.mean()) if region.size else 0.0
            if cov[k] > 0.06: months[ACT[k]].append(c + 1)
        cover.append(cov)
    # which way up? within a month cell the stripes run pink, green, blue, yellow from the top
    rank = {"pink": 0, "green": 1, "blue": 2, "yellow": 3}
    vote = 0
    for c in range(12):
        cx0, cx1 = int(edges[c] + 0.2 * p), int(edges[c + 1] - 0.2 * p)
        mids = {}
        for k, m in loose.items():
            ys_, _ = np.where(m[y0:y1, max(cx0, 0):cx1])
            if len(ys_) > 0.06 * (y1 - y0) * max(cx1 - cx0, 1): mids[k] = ys_.mean()
        for a in mids:
            for b in mids:
                if rank[a] < rank[b] and abs(mids[a] - mids[b]) > 3: vote += 1 if mids[a] < mids[b] else -1
    return {"ok": True, "vote": vote, "months": months, "grid": [float(start), float(p), int(hit)], "edges": edges, "bar": [int(x0), int(y0), int(x1), int(y1)],
            "size": list(im.size), "cover": cover}

if __name__ == "__main__":
    print(json.dumps(read(sys.argv[1], int(sys.argv[2])), indent=None))
