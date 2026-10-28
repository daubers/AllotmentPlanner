"""Photos and video in, georeferenced map tiles out: OpenSfM for the geometry, GDAL for the map.

Runs on the ``mapper`` worker (see worker/Dockerfile). OpenSfM lives in its own virtualenv and is
driven as a subprocess; this module only prepares its dataset, reads its JSON, and shells out to
GDAL. The geometry lives in :mod:`mapping_geo`.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import structlog
import yaml
from flask import current_app
from PIL import Image

from . import detection_geo, media_meta
from . import detector as detector_module
from . import mapping_geo as geo
from .extensions import db
from .mapping_video import video_frame_rate
from .models import MapJob, MapLayer, MapSuggestion, Media
from .storage import get_storage

log = structlog.get_logger(__name__)

OPENSFM_PYTHON = os.environ.get("OPENSFM_PYTHON", "python3")
OPENSFM_MAIN = os.environ.get("OPENSFM_MAIN", "/opt/OpenSfM/bin/opensfm_main.py")

MIN_IMAGES = 5
MIN_GEOTAGGED = 3
GPS_ACCURACY_M = 5.0  # how much OpenSfM trusts each photo's location
MAX_PIXELS = 80_000_000  # output raster size limit; coarser pixels are used beyond this
LOG_LIMIT = 20_000
REACH_PER_METRE_OF_HEIGHT = 12  # ignore ground further away than this many camera heights
FRAME_CANDIDATES = 3  # per video frame wanted, sample this many and keep the sharpest (motion blur)


class JobFailed(Exception):
    """A problem with the input or the result, worded for the person who started the job."""


class JobCancelled(Exception):
    pass


@dataclass(frozen=True)
class Result:
    layer: MapLayer


# --- progress, logging, subprocesses ---------------------------------------------------------


def set_stage(job: MapJob, stage: str) -> None:
    job.stage = stage
    _append_log(job, f"== {stage}")
    db.session.commit()
    log.info("map_job_stage", stage=stage)


def _append_log(job: MapJob, text: str) -> None:
    job.log = (job.log + text.rstrip("\n") + "\n")[-LOG_LIMIT:]


def check_cancelled(job: MapJob) -> None:
    db.session.refresh(job)
    if job.cancel_requested:
        raise JobCancelled


def run(job: MapJob, command: list[str], work: Path, label: str, timeout: float) -> None:
    """Run a subprocess, streaming its output into the job log and honouring cancellation."""
    out_path = work / f"{label}.log"
    started = time.monotonic()
    last_flush, offset = started, 0
    with open(out_path, "wb") as out:
        proc = subprocess.Popen(command, stdout=out, stderr=subprocess.STDOUT, cwd=work)  # noqa: S603
        try:
            while proc.poll() is None:
                time.sleep(1)
                now = time.monotonic()
                if now - last_flush >= 10:
                    offset = _flush_output(job, out_path, offset)
                    check_cancelled(job)
                    last_flush = now
                if now - started > timeout:
                    raise JobFailed(
                        f"{label} took longer than {int(timeout // 60)} minutes and was stopped"
                    )
        except BaseException:
            proc.kill()
            proc.wait()
            raise
    _flush_output(job, out_path, offset)
    db.session.commit()
    if proc.returncode != 0:
        raise JobFailed(f"{label} failed (exit code {proc.returncode}); see the log")


def _flush_output(job: MapJob, path: Path, offset: int) -> int:
    with open(path, "rb") as f:
        f.seek(offset)
        chunk = f.read()
    if chunk:
        _append_log(job, chunk.decode(errors="replace"))
        db.session.commit()
    return offset + len(chunk)


# --- 1. the dataset --------------------------------------------------------------------------


def prepare_dataset(job: MapJob, work: Path) -> int:
    """Download the chosen media into an OpenSfM dataset. Returns the number of images."""
    images = work / "images"
    images.mkdir(parents=True)
    storage = get_storage()
    cfg = current_app.config
    overrides: dict[str, dict] = {}
    geotagged = 0
    frames_total = 0

    for media_id in job.media_ids:
        media = db.session.get(Media, media_id)
        if media is None or media.allotment_id != job.allotment_id or media.status != "ready":
            continue
        if media.kind == "photo":
            ext = media_meta.extension_for("photo", _head(storage, media.storage_key))
            name = f"m{media.id}{ext}"
            storage.download(media.storage_key, str(images / name))
            if media.lat is not None and media.lng is not None:
                geotagged += 1
                overrides[name] = {
                    "gps": {
                        "latitude": media.lat,
                        "longitude": media.lng,
                        # Altitude from phones is unreliable, so every photo is placed at the
                        # stated carrying height; OpenSfM works out the real geometry itself.
                        "altitude": job.camera_height_m,
                        "dop": GPS_ACCURACY_M,
                    }
                }
        else:
            if not media_meta.have_ffmpeg():
                raise JobFailed("This worker has no ffmpeg, so videos can't be used")
            source = work / f"video{media.id}"
            storage.download(media.storage_key, str(source))
            frames = extract_frames(
                source,
                images,
                prefix=f"v{media.id}_",
                fps=cfg["MAPPING_VIDEO_FRAMES_PER_SECOND"],
                limit=cfg["MAPPING_MAX_FRAMES_PER_VIDEO"],
                duration=media.duration_s,
            )
            source.unlink()
            frames_total += len(frames)
            # A video has one location (where it started), not one per frame, so frames carry no
            # GPS: pinning them all to that point would drag the map together. They are placed by
            # matching against the geotagged photos. Each video gets its own camera model.
            for frame in frames:
                overrides[frame] = {"camera": f"video {media.id}"}

    total = len(list(images.iterdir()))
    if total < MIN_IMAGES:
        raise JobFailed(
            f"Only {total} usable images; at least {MIN_IMAGES} overlapping photos "
            "(or enough video) are needed"
        )
    if geotagged < MIN_GEOTAGGED:
        raise JobFailed(
            f"Only {geotagged} of the photos have a location; at least {MIN_GEOTAGGED} are needed "
            "to place and scale the map (a video has only one location, which can't)"
        )
    (work / "exif_overrides.json").write_text(json.dumps(overrides))
    (work / "config.yaml").write_text(yaml.safe_dump(opensfm_config(job, frames_total > 0)))
    return total


def _head(storage, key: str) -> bytes:
    return b"".join(storage.read_range(key, 0, 15))


def opensfm_config(job: MapJob, has_frames: bool = False) -> dict:
    config = {
        "processes": max(1, (os.cpu_count() or 2) - 1),
        "feature_process_size": 2048,
        "use_altitude_tag": True,
        # Hand-held photos keep the camera roughly level; overhead ones look straight down.
        "align_orientation_prior": "vertical" if job.view == "overhead" else "horizontal",
        "undistorted_image_max_size": 3000,
    }
    if has_frames:
        # OpenSfM switches off GPS-based pair selection as soon as any image lacks GPS, and with
        # nothing else configured it then tries every pair. Neighbouring frames (by file name)
        # plus look-alikes from other cameras (bag of words) link the video to the photos.
        config |= {
            "matching_order_neighbors": 6,
            "matching_bow_neighbors": 10,
            "matching_bow_other_cameras": True,
        }
    return config


def sharpness(path: Path) -> float:
    """Variance of a Laplacian over a fixed-size greyscale copy: higher means less blur."""
    with Image.open(path) as img:
        grey = img.convert("L")
        grey = grey.resize((480, max(1, round(480 * grey.height / grey.width))))
    g = np.asarray(grey, dtype=float)
    lap = 4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return float(lap.var())


def sharpest_of_each_group(paths: list[Path], size: int) -> list[Path]:
    """The least blurred frame from each run of ``size`` consecutive ones."""
    return [max(paths[i : i + size], key=sharpness) for i in range(0, len(paths), size)]


def extract_frames(
    video: Path, out_dir: Path, prefix: str, fps: float, limit: int, duration: float | None = None
) -> list[str]:
    """Sample frames from a video as JPEGs, keeping the sharpest of several candidates for each
    sampling point (hand-held video is often blurred). Returns the file names, in order."""
    rate = video_frame_rate(duration, fps, limit)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(  # noqa: S603
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(video),
                "-vf",
                f"fps={rate * FRAME_CANDIDATES},scale='min(2048,iw)':-2",
                "-frames:v",
                str(limit * FRAME_CANDIDATES),
                "-q:v",
                "2",
                str(Path(tmp) / "c%05d.jpg"),
            ],  # fmt: skip
            check=True,
            capture_output=True,
            timeout=900,
        )
        chosen = sharpest_of_each_group(sorted(Path(tmp).glob("c*.jpg")), FRAME_CANDIDATES)[:limit]
        names = []
        for n, path in enumerate(chosen, start=1):
            name = f"{prefix}{n:04d}.jpg"
            shutil.move(path, out_dir / name)
            names.append(name)
        return names


# --- 2. OpenSfM ------------------------------------------------------------------------------

STEPS = [
    ("features", ["extract_metadata", "detect_features"]),
    ("matching", ["match_features", "create_tracks"]),
    ("reconstructing", ["reconstruct", "undistort"]),
]


def reconstruct(job: MapJob, work: Path) -> None:
    timeout = current_app.config["MAPPING_TIMEOUT_SECONDS"]
    for stage, commands in STEPS:
        set_stage(job, stage)
        for command in commands:
            check_cancelled(job)
            run(job, [OPENSFM_PYTHON, OPENSFM_MAIN, command, str(work)], work, command, timeout)


# --- 3. orthophoto ---------------------------------------------------------------------------


@dataclass
class Placed:
    source: Path  # cropped, undistorted JPEG
    gcps: list[tuple[float, float, float, float]]
    distance: float  # camera to the middle of what it sees; far shots are drawn first
    resolution: float


def placed_shots(job: MapJob, work: Path) -> tuple[list[Placed], geo.Reconstruction, tuple]:
    rec = geo.load_reconstruction(
        str(work / "undistorted" / "reconstruction.json"), str(work / "reference_lla.json")
    )
    if len(rec.shots) < MIN_GEOTAGGED:
        raise JobFailed(
            f"Only {len(rec.shots)} of the images could be placed together; "
            "take more photos that overlap each other and show the same ground"
        )
    plane = geo.fit_ground_plane(rec.points)
    src_dir = work / "ortho" / "src"
    src_dir.mkdir(parents=True)
    placed: list[Placed] = []
    for i, shot in enumerate(rec.shots):
        image = work / "undistorted" / "images" / shot.name
        if not image.exists():
            continue
        a, b, c = plane
        centre = shot.centre
        height = centre[2] - (a * centre[0] + b * centre[1] + c)
        crop = geo.ground_crop(shot, plane, max_range=max(10.0, REACH_PER_METRE_OF_HEIGHT * height))
        if crop is None:
            continue
        gcps = geo.gcp_grid(shot, plane, crop, rec.reference)
        with Image.open(image) as img:
            path = src_dir / f"{i}.jpg"
            img.convert("RGB").crop((crop.x0, crop.y0, crop.x1, crop.y1)).save(
                path, "JPEG", quality=92
            )
        mid = geo.ground_hits(
            shot, plane, [[(crop.x0 + crop.x1) / 2, (crop.y0 + crop.y1) / 2]], float("inf")
        )[0]
        placed.append(
            Placed(
                path,
                gcps,
                float(np.linalg.norm(mid - centre)),
                geo.ground_resolution(shot, plane, crop),
            )
        )
    if len(placed) < MIN_GEOTAGGED:
        raise JobFailed(
            "Too few photos show enough ground to build a map; try photos angled further down"
        )
    return placed, rec, plane


def build_orthophoto(
    job: MapJob, work: Path
) -> tuple[Path, tuple[float, float, float, float], float, float]:
    """Warp every photo onto the ground and mosaic them. Returns (GeoTIFF, mercator bounds,
    ground resolution in metres, latitude of the middle)."""
    placed, rec, _plane = placed_shots(job, work)
    set_stage(job, "orthophoto")
    lons = np.array([g[2] for p in placed for g in p.gcps])
    lats = np.array([g[3] for p in placed for g in p.gcps])
    xs, ys = geo.lonlat_to_mercator(lons, lats)
    minx, maxx, miny, maxy = float(xs.min()), float(xs.max()), float(ys.min()), float(ys.max())
    lat_mid = float(lats.mean())
    resolution = geo.choose_resolution([p.resolution for p in placed])
    pixel = geo.mercator_pixel_size(resolution, lat_mid)
    pixels = ((maxx - minx) / pixel) * ((maxy - miny) / pixel)
    if pixels > MAX_PIXELS:  # a very large area: use coarser pixels rather than fail
        scale = (pixels / MAX_PIXELS) ** 0.5
        pixel, resolution = pixel * scale, resolution * scale
    ortho = work / "ortho"
    timeout = current_app.config["MAPPING_TIMEOUT_SECONDS"]
    vrts = []
    for p in sorted(placed, key=lambda s: -s.distance):  # nearest photos are drawn last, on top
        check_cancelled(job)
        vrt = p.source.with_suffix(".vrt")
        gcp_args = [str(v) for g in p.gcps for v in ("-gcp", g[0], g[1], g[2], g[3])]
        run(
            job,
            [
                "gdal_translate",
                "-q",
                "-of",
                "VRT",
                "-a_srs",
                "EPSG:4326",
                *gcp_args,
                str(p.source),
                str(vrt),
            ],
            work,
            "gdal_translate",
            timeout,
        )
        vrts.append(str(vrt))
    tif = ortho / "ortho.tif"
    run(
        job,
        [
            "gdalwarp",
            "-q",
            "-overwrite",
            "-t_srs",
            "EPSG:3857",
            "-te",
            str(minx),
            str(miny),
            str(maxx),
            str(maxy),
            "-tr",
            str(pixel),
            str(pixel),
            "-tps",
            "-r",
            "bilinear",
            "-dstalpha",
            "-multi",
            "-wo",
            "NUM_THREADS=ALL_CPUS",
            "-co",
            "TILED=YES",
            "-co",
            "COMPRESS=DEFLATE",
            "-co",
            "BIGTIFF=IF_SAFER",
            *vrts,
            str(tif),
        ],  # fmt: skip
        work,
        "gdalwarp",
        timeout,
    )
    job.shots_used = len(placed)
    return tif, (minx, miny, maxx, maxy), resolution, lat_mid


# --- 4. tiles and the layer ------------------------------------------------------------------


def make_tiles(job: MapJob, work: Path, tif: Path, min_zoom: int, max_zoom: int) -> Path:
    set_stage(job, "tiling")
    tiles = work / "tiles"
    run(
        job,
        [
            "gdal2tiles.py",
            "--xyz",
            "-z",
            f"{min_zoom}-{max_zoom}",
            "-r",
            "bilinear",
            "-w",
            "none",
            f"--processes={max(1, os.cpu_count() or 1)}",
            str(tif),
            str(tiles),
        ],  # fmt: skip
        work,
        "gdal2tiles",
        current_app.config["MAPPING_TIMEOUT_SECONDS"],
    )
    return tiles


def store_layer(job: MapJob, tiles: Path, bounds, min_zoom: int, max_zoom: int) -> MapLayer:
    set_stage(job, "saving")
    minx, miny, maxx, maxy = bounds
    (west, east), (south, north) = geo.mercator_to_lonlat([minx, maxx], [miny, maxy])
    layer = MapLayer(
        allotment_id=job.allotment_id,
        job_id=job.id,
        name=job.name,
        west=float(west),
        south=float(south),
        east=float(east),
        north=float(north),
        min_zoom=min_zoom,
        max_zoom=max_zoom,
    )
    db.session.add(layer)
    db.session.flush()
    storage, count = get_storage(), 0
    for path in tiles.rglob("*.png"):
        rel = path.relative_to(tiles).as_posix()  # z/x/y.png
        storage.put(f"{layer.tile_prefix}/{rel}", str(path), "image/png")
        count += 1
    if not count:
        raise JobFailed("No map tiles were produced")
    layer.tile_count = count
    return layer


# --- 5. recognising objects -------------------------------------------------------------------


def choose_shots(shots: list[geo.Shot], limit: int) -> list[geo.Shot]:
    """Which photos to look at: all the real photos if they fit, else an even spread of them;
    video frames only fill whatever room is left (they are many and near-duplicates)."""
    photos = [s for s in shots if not s.name.startswith("v")]
    frames = [s for s in shots if s.name.startswith("v")]

    def spread(items: list[geo.Shot], n: int) -> list[geo.Shot]:
        if n <= 0 or not items:
            return []
        if len(items) <= n:
            return items
        return [items[int(i * len(items) / n)] for i in range(n)]

    chosen = spread(photos, limit)
    return chosen + spread(frames, limit - len(chosen))


def suggestion_name(label: str, number: int, total: int) -> str:
    return f"{label} {number}" if total > 1 else label


def detect_objects(job: MapJob, work: Path, detector=None) -> int:
    """Find objects in the placed photos, put them on the ground and save them as suggestions
    to review. Returns how many were found."""
    set_stage(job, "detecting")
    rec = geo.load_reconstruction(
        str(work / "undistorted" / "reconstruction.json"), str(work / "reference_lla.json")
    )
    plane = geo.fit_ground_plane(rec.points)
    shots = choose_shots(rec.shots, current_app.config["MAPPING_DETECT_MAX_SHOTS"])
    detector = detector or detector_module.get_detector()
    observations: list[detection_geo.Observation] = []
    for n, shot in enumerate(shots, start=1):
        check_cancelled(job)
        path = work / "undistorted" / "images" / shot.name
        if not path.exists():
            continue
        with Image.open(path) as image:
            found = detector.detect(image)
        for d in found:
            fp = detection_geo.footprint_from_mask(
                shot, plane, d.mask, d.score, d.type.shape, scale=d.scale
            )
            if fp:
                observations.append(
                    detection_geo.Observation(d.type.name, d.type.kind, d.type.shape, fp, shot.name)
                )
        _append_log(job, f"looked at photo {n} of {len(shots)}: {len(found)} objects")
        db.session.commit()
    fused = detection_geo.fuse(observations)
    # Suggestions from an earlier run are replaced by this one.
    db.session.query(MapSuggestion).filter_by(
        allotment_id=job.allotment_id, status="pending"
    ).update({"status": "dismissed"})
    totals: dict[str, int] = {}
    for g in fused:
        totals[g.label] = totals.get(g.label, 0) + 1
    counters: dict[str, int] = {}
    for g in fused:
        counters[g.label] = counters.get(g.label, 0) + 1
        ring = detection_geo.outline(g)
        lon, lat = geo.enu_to_lonlat(
            np.array([p[0] for p in ring]), np.array([p[1] for p in ring]), rec.reference
        )
        if g.shape == "circle":
            clon, clat = geo.enu_to_lonlat(g.x, g.y, rec.reference)
            geometry = {"type": "Point", "coordinates": [float(clon), float(clat)]}
            radius = round(max(g.width, g.depth) / 2, 2)
        else:
            coords = [[float(a), float(b)] for a, b in zip(lon, lat, strict=True)]
            geometry = {"type": "Polygon", "coordinates": [[*coords, coords[0]]]}
            radius = None
        db.session.add(
            MapSuggestion(
                allotment_id=job.allotment_id,
                job_id=job.id,
                kind=g.kind,
                name=suggestion_name(g.label, counters[g.label], totals[g.label]),
                geometry=geometry,
                radius_m=radius,
                confidence=g.confidence,
                views=g.views,
            )
        )
    job.objects_found = len(fused)
    db.session.commit()
    return len(fused)


def process(job: MapJob, work: Path) -> MapLayer | None:
    """The whole pipeline for one job. Raises JobFailed / JobCancelled. Returns the photo overlay
    layer if one was asked for."""
    set_stage(job, "preparing")
    job.shots_total = prepare_dataset(job, work)
    db.session.commit()
    reconstruct(job, work)
    check_cancelled(job)
    if job.detect_objects:
        detect_objects(job, work)
        check_cancelled(job)
    layer = None
    if job.overlay:
        tif, bounds, resolution, lat_mid = build_orthophoto(job, work)
        max_zoom = geo.zoom_for_resolution(resolution, lat_mid)
        min_zoom = max(10, max_zoom - 6)
        tiles = make_tiles(job, work, tif, min_zoom, max_zoom)
        check_cancelled(job)
        layer = store_layer(job, tiles, bounds, min_zoom, max_zoom)
        layer.visible = (
            False  # experimental, and a mess for hand-held photos: opt in on the Layers page
        )
    job.finished_at = datetime.now(UTC)
    return layer
