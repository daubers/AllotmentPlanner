"""End-to-end check of the map-from-photos pipeline against a scene with a known answer.

Renders a textured ground plane from a grid of overhead cameras (with GPS EXIF and some noise),
uploads the photos through the API, builds a map with the real OpenSfM + GDAL worker, then
compares the resulting tiles with the original texture, scanning for any scale or rotation error.

The photos' GPS is the only thing that fixes the map's scale, so GPS jitter shows up as a scale
error of roughly noise / (camera spread * sqrt(photos)): about 1% at the default 0.3 m, about 4%
at phone-quality 1.5 m. The default checks the pipeline itself; try ``GPS_NOISE=1.5`` to see what
a real phone gives (the check then fails on scale, which is the expected behaviour).

    make up mapper && make mapping-check        # needs numpy, Pillow and requests
    KEEP=1 ...                                  # keep the allotment to look at it in the app
    SCENARIO=video ...                          # 9 geotagged photos + a walk-through video (GPS_NOISE 0.05)

The video scenario adds a camera path with no GPS (as a phone video has none per frame, just one
location at the start), some frames motion-blurred. It checks the video frames are placed by
matching them to the photos, extend the map beyond what the photos cover, and line up with the
true texture there.
"""

import io
import math
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter

API = "http://localhost:8000/api/v1"
CENTRE = (51.5, -0.12)  # latitude, longitude of the scene centre
SCENE = (44.0, 34.0)  # metres east-west, north-south
TEXTURE_RES = 0.01  # metres per texture pixel
PHOTO = (2000, 1500)
FOCAL = 0.8  # normalised by the long side
HEIGHT = 12.0
GRID_X = [-10, -5, 0, 5, 10]
GRID_Y = [-8, -4, 0, 4, 8]
SCENARIO = os.environ.get("SCENARIO", "photos")
# GPS jitter in metres per axis (phones are 1-3). The video scenario defaults to almost none: only
# nine photos anchor its scale, so realistic jitter would swamp what it is meant to check.
GPS_NOISE = float(os.environ.get("GPS_NOISE", "0.05" if SCENARIO == "video" else "0.3"))
VIDEO_FRAME = (1280, 960)
VIDEO_FPS = 5
VIDEO_SPEED = 3.0  # metres per second along the path


def metres_per_degree(lat: float) -> tuple[float, float]:
    phi = math.radians(lat)
    return (
        111132.92 - 559.82 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi),
        111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi),
    )


def make_texture(rng: np.random.Generator) -> Image.Image:
    """Detailed, non-repeating ground: multi-scale noise plus scattered blobs and lines."""
    w, h = round(SCENE[0] / TEXTURE_RES), round(SCENE[1] / TEXTURE_RES)
    acc = np.zeros((h, w, 3))
    for cell, weight in [(512, 1.0), (256, 1.0), (128, 0.9), (64, 0.8), (32, 0.7), (16, 0.6), (8, 0.5)]:
        small = rng.random((h // cell + 2, w // cell + 2, 3))
        acc += weight * np.asarray(
            Image.fromarray((small * 255).astype("uint8")).resize((w + cell, h + cell), Image.BICUBIC)
        )[:h, :w] / 255.0
    acc = (acc - acc.min()) / (acc.max() - acc.min())
    img = Image.fromarray((acc * 255).astype("uint8"))
    draw = ImageDraw.Draw(img)
    for _ in range(9000):
        x, y, r = rng.integers(0, w), rng.integers(0, h), rng.integers(3, 30)
        colour = tuple(int(c) for c in rng.integers(0, 255, 3))
        if rng.random() < 0.6:
            draw.ellipse([x - r, y - r, x + r, y + r], fill=colour)
        else:
            draw.rectangle([x - r, y - r // 2, x + r, y + r // 2], fill=colour)
    for _ in range(1500):
        x, y = rng.integers(0, w), rng.integers(0, h)
        dx, dy = rng.integers(-120, 120, 2)
        draw.line([x, y, x + dx, y + dy], fill=tuple(int(c) for c in rng.integers(0, 255, 3)), width=int(rng.integers(2, 7)))
    return img


def camera_rotation(rng: np.random.Generator) -> np.ndarray:
    """Looking down with image-up = north, plus a couple of degrees of wobble."""
    base = np.array([[1.0, 0, 0], [0, -1, 0], [0, 0, -1]])
    wobble = np.radians(rng.normal(0, 1.5, 3))
    kx = np.array([[0, -wobble[2], wobble[1]], [wobble[2], 0, -wobble[0]], [-wobble[1], wobble[0], 0]])
    return (np.eye(3) + kx) @ base  # first-order rotation is plenty for ~1.5 degrees


def render(
    texture: Image.Image, centre: np.ndarray, rotation: np.ndarray, frame: tuple[int, int] = PHOTO
) -> Image.Image:
    """The photo a camera at ``centre`` would take of the textured ground plane z = 0."""
    w, h = frame
    size = max(w, h)
    corners = [(0, 0), (w - 1, 0), (w - 1, h - 1), (0, h - 1)]
    ground = []
    for px, py in corners:
        ray = rotation.T @ np.array([(px - w / 2 + 0.5) / size / FOCAL, (py - h / 2 + 0.5) / size / FOCAL, 1.0])
        lam = -centre[2] / ray[2]
        east, north = centre[0] + lam * ray[0], centre[1] + lam * ray[1]
        ground.append(((east + SCENE[0] / 2) / TEXTURE_RES, (SCENE[1] / 2 - north) / TEXTURE_RES))
    # homography from output pixels to texture pixels, solved from the four corners
    rows, rhs = [], []
    for (x, y), (u, v) in zip(corners, ground, strict=True):
        rows += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        rhs += [u, v]
    coeffs = np.linalg.solve(np.array(rows, float), np.array(rhs, float))
    return texture.transform(frame, Image.PERSPECTIVE, tuple(coeffs), Image.BICUBIC)


def dms(value: float) -> tuple[float, float, float]:
    value = abs(value)
    d = int(value)
    m = int((value - d) * 60)
    return float(d), float(m), round((value - d - m / 60) * 3600, 4)


def jpeg(image: Image.Image, lat: float, lng: float, index: int) -> bytes:
    exif = Image.Exif()
    exif[0x010F], exif[0x0110] = "SynthCam", "S1"
    exif.get_ifd(0x8769)[0xA405] = round(FOCAL * 36)  # 35mm-equivalent focal length
    stamp = f"2026:10:27 14:{index // 60:02d}:{index % 60:02d}"
    exif[0x0132] = stamp
    exif.get_ifd(0x8769)[0x9003] = stamp
    g = exif.get_ifd(0x8825)
    g[1], g[2] = ("N" if lat >= 0 else "S"), dms(lat)
    g[3], g[4] = ("E" if lng >= 0 else "W"), dms(lng)
    g[5], g[6] = 0, 85.0 + HEIGHT  # altitude above sea level: deliberately unrelated to the scene
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=92, exif=exif)
    return buf.getvalue()


def make_photos(rng: np.random.Generator, texture: Image.Image, grid_x, grid_y) -> list[bytes]:
    lat_m, lon_m = metres_per_degree(CENTRE[0])
    photos = []
    for i, (x, y) in enumerate((x, y) for y in grid_y for x in grid_x):
        centre = np.array([x + rng.normal(0, 0.15), y + rng.normal(0, 0.15), HEIGHT + rng.normal(0, 0.3)])
        image = render(texture, centre, camera_rotation(rng))
        noisy_e, noisy_n = x + rng.normal(0, GPS_NOISE), y + rng.normal(0, GPS_NOISE)
        photos.append(jpeg(image, CENTRE[0] + noisy_n / lat_m, CENTRE[1] + noisy_e / lon_m, i))
    return photos


# A walk over the plot: along the north side, down the east edge, back along the south side.
VIDEO_PATH = [(-14.0, 9.0), (14.0, 9.0), (14.0, -9.0), (-14.0, -9.0)]


def video_positions() -> list[tuple[float, float]]:
    """Camera positions, one per video frame, moving at VIDEO_SPEED along VIDEO_PATH."""
    step = VIDEO_SPEED / VIDEO_FPS
    points = []
    for (x0, y0), (x1, y1) in zip(VIDEO_PATH, VIDEO_PATH[1:], strict=False):
        length = math.hypot(x1 - x0, y1 - y0)
        for k in range(int(length / step)):
            points.append((x0 + (x1 - x0) * k * step / length, y0 + (y1 - y0) * k * step / length))
    return points


def encode_video(frames: Path, dest: Path) -> None:
    """H.264 mp4 from numbered JPEGs, with a start location tag like a phone writes. Uses a local
    ffmpeg if one works, otherwise the one in the mapper image."""
    args = [
        "-v", "error", "-y", "-framerate", str(VIDEO_FPS), "-i", f"{frames}/f%04d.jpg",
        "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
        "-metadata", "location=+51.5000-000.1200/", "-movflags", "+faststart",
    ]  # fmt: skip
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True, timeout=10)
        subprocess.run(["ffmpeg", *args, str(dest)], check=True, timeout=600)
    except (OSError, subprocess.SubprocessError):
        root = Path(__file__).resolve().parents[1]
        subprocess.run(
            ["docker", "compose", "--profile", "mapping", "run", "--rm", "--no-deps", "-v", f"{frames.parent}:/w",
             "--entrypoint", "ffmpeg", "mapper", *args[:5], "-i", "/w/frames/f%04d.jpg", *args[7:], "/w/walk.mp4"],
            check=True, timeout=900, cwd=root,
        )  # fmt: skip


def make_video(rng: np.random.Generator, texture: Image.Image) -> bytes:
    """A walk-through: overhead frames along VIDEO_PATH, some motion-blurred, no GPS anywhere."""
    with tempfile.TemporaryDirectory() as tmp:
        frames = Path(tmp) / "frames"
        frames.mkdir()
        for i, (x, y) in enumerate(video_positions(), start=1):
            centre = np.array([x + rng.normal(0, 0.1), y + rng.normal(0, 0.1), HEIGHT + rng.normal(0, 0.2)])
            image = render(texture, centre, camera_rotation(rng), VIDEO_FRAME)
            if i % 5 == 2:  # one frame in five is smeared, as hand-held video often is
                image = image.filter(ImageFilter.GaussianBlur(4))
            image.save(frames / f"f{i:04d}.jpg", quality=92)
        encode_video(frames, Path(tmp) / "walk.mp4")
        return (Path(tmp) / "walk.mp4").read_bytes()


def make_media(rng: np.random.Generator) -> tuple[list[bytes], bytes | None]:
    texture = make_texture(rng)
    texture.save(Path(tempfile.gettempdir()) / "mapping_check_texture.png")
    if SCENARIO == "video":
        photos = make_photos(rng, texture, [-5, 0, 5], [-4, 0, 4])
        return photos, make_video(rng, texture)
    return make_photos(rng, texture, GRID_X, GRID_Y), None


# --- driving the API -------------------------------------------------------------------------


def wait(what: str, fn, timeout: float, every: float = 3):
    end = time.time() + timeout
    while time.time() < end:
        value = fn()
        if value:
            return value
        time.sleep(every)
    sys.exit(f"FAIL: timed out waiting for {what}")


def run_pipeline(photos: list[bytes], video: bytes | None) -> tuple[dict, dict, dict, str]:
    r = requests.post(
        f"{API}/auth/register",
        json={"email": f"mapcheck{uuid.uuid4().hex[:6]}@example.com", "display_name": "Mapcheck", "password": "password123"},
    )
    r.raise_for_status()
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    pid = requests.post(f"{API}/allotments", json={"name": "Mapping check"}, headers=headers).json()["id"]
    base = f"{API}/allotments/{pid}"
    print(f"allotment {pid}: uploading {len(photos)} photos")
    for i, data in enumerate(photos):
        requests.post(f"{base}/media", files={"file": (f"s{i}.jpg", data, "image/jpeg")}, headers=headers).raise_for_status()
    if video:
        print(f"uploading a {len(video) / 1e6:.1f} MB video")
        up = requests.post(f"{base}/media", files={"file": ("walk.mp4", video, "video/mp4")}, headers=headers)
        up.raise_for_status()
    wait("uploads to be processed", lambda: all(m["status"] == "ready" for m in requests.get(f"{base}/media?limit=500", headers=headers).json()), 300)
    resp = requests.post(f"{base}/map-jobs", json={"name": "Synthetic", "view": "overhead", "camera_height_m": HEIGHT}, headers=headers)
    resp.raise_for_status()
    job_id, stage = resp.json()["id"], None
    start = time.time()

    def poll():
        nonlocal stage
        job = requests.get(f"{base}/map-jobs/{job_id}", headers=headers).json()
        if job["stage"] != stage:
            stage = job["stage"]
            print(f"  [{int(time.time() - start):4d}s] {job['status']}: {stage or 'waiting for the mapper worker'}")
        return job if job["status"] in ("ready", "failed", "cancelled") else None

    job = wait("the map job", poll, 3600, every=5)
    if job["status"] != "ready":
        print(job["log"][-3000:])
        sys.exit(f"FAIL: job {job['status']}: {job['error']}")
    print(f"  used {job['shots_used']} of {job['shots_total']} images")
    [layer] = requests.get(f"{base}/layers", headers=headers).json()
    return layer, job, {"headers": headers, "base": base}, f"http://localhost:8000{layer['tile_url']}"


# --- checking the result ---------------------------------------------------------------------


class Tiles:
    def __init__(self, template: str, zoom: int):
        self.template, self.zoom, self.cache = template, zoom, {}

    def tile(self, x: int, y: int):
        if (x, y) not in self.cache:
            url = self.template.format(z=self.zoom, x=x, y=y)
            self.cache[(x, y)] = np.asarray(Image.open(io.BytesIO(requests.get(url).content)).convert("RGBA"))
        return self.cache[(x, y)]

    def sample(self, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
        """Grey values at lon/lat (NaN where the layer is transparent), nearest-pixel."""
        n = 2**self.zoom
        px = (lon + 180) / 360 * n * 256
        py = (1 - np.log(np.tan(np.radians(lat)) + 1 / np.cos(np.radians(lat))) / math.pi) / 2 * n * 256
        out = np.full(lon.shape, np.nan)
        for tx in np.unique((px // 256).astype(int)):
            for ty in np.unique((py // 256).astype(int)):
                sel = ((px // 256).astype(int) == tx) & ((py // 256).astype(int) == ty)
                tile = self.tile(tx, ty)
                ix, iy = (px[sel] - tx * 256).astype(int), (py[sel] - ty * 256).astype(int)
                rgba = tile[iy.clip(0, 255), ix.clip(0, 255)]
                grey = rgba[:, :3].mean(axis=1)
                grey[rgba[:, 3] < 128] = np.nan
                out[sel] = grey
        return out


def ncc_search(big: np.ndarray, small: np.ndarray, radius: int) -> tuple[int, int, float]:
    """Best normalised correlation of ``small`` inside ``big`` over shifts up to ``radius`` px."""
    sh, sw = small.shape
    cy, cx = (big.shape[0] - sh) // 2, (big.shape[1] - sw) // 2
    s = small - small.mean()
    best = (0, 0, -1.0)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            win = big[cy + dy : cy + dy + sh, cx + dx : cx + dx + sw]
            if np.isnan(win).mean() > 0.05:
                continue
            w = np.nan_to_num(win, nan=float(np.nanmean(win)))
            w = w - w.mean()
            denom = math.sqrt((w * w).sum() * (s * s).sum())
            if denom:
                score = float((w * s).sum() / denom)
                if score > best[2]:
                    best = (dx, dy, score)
    return best


RES = 0.1  # compare at 10 cm per pixel


def compare_region(tiles, texture: Image.Image, lon_m: float, lat_m: float, centre, size, margin, scans):
    """Match a window of the true texture against the map around ``centre`` (metres east, north of
    the scene centre). Returns (east offset m, north offset m, correlation, ortho, truth, scan
    results). ``scans`` also tries the window scaled and rotated to expose a wrong scale/rotation."""
    (ce, cn), (w, h) = centre, size
    gx = np.arange(ce - (w / 2 + margin), ce + (w / 2 + margin), RES) + RES / 2
    gy = np.arange(cn + (h / 2 + margin), cn - (h / 2 + margin), -RES) - RES / 2
    east, north = np.meshgrid(gx, gy)
    parts = []  # each 10 cm cell is the mean of 2 x 2 layer pixels, to match the averaged truth
    for ox in (-0.025, 0.025):
        for oy in (-0.025, 0.025):
            parts.append(tiles.sample(CENTRE[1] + (east + ox) / lon_m, CENTRE[0] + (north + oy) / lat_m))
    with np.errstate(all="ignore"):
        ortho = np.nanmean(np.stack(parts), axis=0)
    fine = texture.resize((texture.width // 5, texture.height // 5), Image.BOX)  # 5 cm per pixel
    out_w, out_h = round(w / RES), round(h / RES)
    k = RES / (TEXTURE_RES * 5)  # source pixels per output pixel

    def truth(scale: float = 1.0, angle: float = 0.0) -> np.ndarray:
        """The window seen ``scale`` times too big and turned by ``angle`` degrees."""
        t = math.radians(angle)
        a, b, d, e = scale * k * math.cos(t), -scale * k * math.sin(t), scale * k * math.sin(t), scale * k * math.cos(t)
        cx, cy = out_w / 2, out_h / 2
        tx, ty = fine.width / 2 + ce / (TEXTURE_RES * 5), fine.height / 2 - cn / (TEXTURE_RES * 5)
        coeffs = (a, b, tx - (a * cx + b * cy), d, e, ty - (d * cx + e * cy))
        return np.asarray(fine.transform((out_w, out_h), Image.AFFINE, coeffs, Image.BILINEAR), float)

    radius = round(margin / RES)
    dx, dy, score = ncc_search(ortho, truth(), radius)
    found = {}
    if scans:
        found["scales"] = {s_: ncc_search(ortho, truth(scale=s_), radius)[2] for s_ in (0.96, 0.98, 0.99, 1.0, 1.01, 1.02, 1.04)}
        found["angles"] = {a_: ncc_search(ortho, truth(angle=a_), radius)[2] for a_ in (-2.0, -1.0, 0.0, 1.0, 2.0)}
    return dx * RES, -dy * RES, score, ortho[radius : radius + out_h, radius : radius + out_w], truth(), found


def check(layer: dict, template: str, job: dict) -> bool:
    lat_m, lon_m = metres_per_degree(CENTRE[0])
    west, south, east, north = layer["bounds"]
    width_m, height_m = (east - west) * lon_m, (north - south) * lat_m
    off_e, off_n = ((west + east) / 2 - CENTRE[1]) * lon_m, ((south + north) / 2 - CENTRE[0]) * lat_m
    print(f"scenario {SCENARIO}, GPS noise {GPS_NOISE} m")
    print(f"layer {width_m:.1f} x {height_m:.1f} m, centred {off_e:+.1f} m E / {off_n:+.1f} m N of the scene centre")
    print(f"zoom {layer['min_zoom']}-{layer['max_zoom']}, {layer['tile_count']} tiles")
    ok = True
    if SCENARIO == "video":
        # photos alone would give about 25 x 19 m; the video frames reach about 43 x 29 m
        sizes = (38 <= width_m <= 48, 26 <= height_m <= 34)
        wanted = "about 43 x 29 m, so the video frames were placed"
        if job["shots_used"] < 0.85 * job["shots_total"]:
            print(f"FAIL: only {job['shots_used']} of {job['shots_total']} images were placed")
            ok = False
    else:
        sizes = (28 <= width_m <= 40, 22 <= height_m <= 32)  # a 20 x 16 m camera grid, 15 x 11 m views
        wanted = "about 35 x 27 m"
    if not all(sizes):
        print(f"FAIL: layer size is not what the camera layout should produce ({wanted})")
        ok = False
    if math.hypot(off_e, off_n) > 4:
        print("FAIL: layer is not centred on the scene")
        ok = False

    texture = Image.open(Path(tempfile.gettempdir()) / "mapping_check_texture.png").convert("L")
    tiles = Tiles(template, layer["max_zoom"])
    de, dn, score, ortho, truth, found = compare_region(tiles, texture, lon_m, lat_m, (0, 0), (12.0, 8.0), 4.0, scans=True)
    print(f"middle of the plot: best match at {de:+.1f} m E / {dn:+.1f} m N, correlation {score:.2f}")
    print("  scale scan:   " + "  ".join(f"{s_:.2f}->{v:.2f}" for s_, v in found["scales"].items()))
    print("  rotation scan:" + "  ".join(f"{a_:+.0f}deg->{v:.2f}" for a_, v in found["angles"].items()))
    best_scale, best_angle = max(found["scales"], key=found["scales"].get), max(found["angles"], key=found["angles"].get)
    side = np.hstack([np.nan_to_num(ortho, nan=0.0), truth])
    Image.fromarray(side.astype("uint8")).resize((side.shape[1] * 4, side.shape[0] * 4), Image.NEAREST).save(
        Path(tempfile.gettempdir()) / "mapping_check_result.png"
    )
    print(f"  side-by-side (map | truth): {Path(tempfile.gettempdir()) / 'mapping_check_result.png'}")
    if abs(best_scale - 1.0) > 0.011 or abs(best_angle) > 1.0:
        print(f"FAIL: the map looks scaled by {best_scale} or rotated by {best_angle} degrees")
        ok = False
    # A scale, rotation or mirror error drops this to chance (about 0); seams and resampling of the
    # 1 cm-detail test scene at 10 cm cost some correlation even when the geometry is right.
    if score < 0.5:
        print("FAIL: the map does not match the scene")
        ok = False
    if math.hypot(de, dn) > 4:
        print("FAIL: the map is displaced by more than the GPS noise allows")
        ok = False

    if SCENARIO == "video":
        # A strip north of anything the photos cover (they end at about +9.6 m): only video frames
        # drew it, and they had no GPS, so this is where the matching to the photos is tested.
        de, dn, score, ortho, truth, _ = compare_region(tiles, texture, lon_m, lat_m, (0, 11.6), (16.0, 2.6), 1.2, scans=False)
        print(f"video-only strip:   best match at {de:+.1f} m E / {dn:+.1f} m N, correlation {score:.2f}")
        side = np.hstack([np.nan_to_num(ortho, nan=0.0), truth])
        Image.fromarray(side.astype("uint8")).resize((side.shape[1] * 4, side.shape[0] * 4), Image.NEAREST).save(
            Path(tempfile.gettempdir()) / "mapping_check_video_strip.png"
        )
        if score < 0.4:
            print("FAIL: the part of the map drawn from video does not match the scene")
            ok = False
        if math.hypot(de, dn) > 1.2:
            print("FAIL: the video part is displaced relative to the true position")
            ok = False
    return ok


def main() -> None:
    rng = np.random.default_rng(7)
    print("rendering the synthetic scene")
    photos, video = make_media(rng)
    layer, job, ctx, template = run_pipeline(photos, video)
    ok = check(layer, template, job)
    if os.environ.get("KEEP"):
        print(f"kept allotment: {ctx['base']}")
    else:
        requests.delete(ctx["base"], headers=ctx["headers"])
    print("PASS" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
