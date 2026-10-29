"""Photos and video in, georeferenced map tiles out: OpenSfM for the geometry, GDAL for the map.

Runs on the ``mapper`` worker (see worker/Dockerfile). OpenSfM lives in its own virtualenv and is
driven as a subprocess; this module only prepares its dataset, reads its JSON, and shells out to
GDAL. The geometry lives in :mod:`mapping_geo`.
"""

import json
import math
import os
import re
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

from . import boundary as boundary_fit
from . import calibration, detection_geo, media_meta, plot_boundary, video_telemetry
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
STALE_MIN_PHOTOS = 4  # this many photos at one place, over this long, mean the GPS is stuck
STALE_MIN_SPAN_S = 60
GPS_ACCURACY_M = 5.0  # how much OpenSfM trusts each photo's location
MAX_PIXELS = 80_000_000  # output raster size limit; coarser pixels are used beyond this
LOG_LIMIT = 20_000
REACH_PER_METRE_OF_HEIGHT = 12  # ignore ground further away than this many camera heights
STATIC_FRAME_DIFF = 2.0  # mean grey-level difference (of 255) below which a frame repeats the last
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
    headings: dict[str, float] = {}
    photo_fixes: dict[str, tuple[float, float, datetime | None, str | None]] = {}

    for media_id in job.media_ids:
        media = db.session.get(Media, media_id)
        if media is None or media.allotment_id != job.allotment_id or media.status != "ready":
            continue
        if media.kind == "photo":
            ext = media_meta.extension_for("photo", _head(storage, media.storage_key))
            name = f"m{media.id}{ext}"
            storage.download(media.storage_key, str(images / name))
            if media.heading is not None:
                headings[name] = media.heading
            if media.lat is not None and media.lng is not None:
                photo_fixes[name] = (media.lat, media.lng, media.taken_at, media.position_source)
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
            track = video_telemetry.read_track(source, media.duration_s)
            source.unlink()
            frames_total += len(frames)
            if track and not video_telemetry.moves(track):
                _append_log(job, f"video {media.id}: its GPS track never moves, so it was ignored")
                track = []
            placed = 0
            for frame, t in frames:
                # Each video gets its own camera model. A GoPro records a GPS track, which locates
                # each frame; a phone video has only the one location (where it started), and
                # pinning every frame to that would drag the map together, so those frames are
                # placed by matching against the photos instead.
                overrides[frame] = {"camera": f"video {media.id}"}
                where = video_telemetry.position_at(track, t) if track else None
                if where is not None:
                    placed += 1
                    overrides[frame]["gps"] = {
                        "latitude": where[0],
                        "longitude": where[1],
                        "altitude": job.camera_height_m,
                        "dop": GPS_ACCURACY_M,
                    }
            if placed:
                geotagged += placed
                _append_log(
                    job,
                    f"video {media.id}: {placed} of {len(frames)} frames located by its GPS track",
                )

    for name, (lat, lng) in photo_locations(photo_fixes, job).items():
        geotagged += 1
        overrides[name] = {
            "gps": {
                "latitude": lat,
                "longitude": lng,
                # Altitude from phones is unreliable, so every photo is placed at the stated
                # carrying height; OpenSfM works out the real geometry itself.
                "altitude": job.camera_height_m,
                "dop": GPS_ACCURACY_M,
            }
        }

    total = len(list(images.iterdir()))
    if total < MIN_IMAGES:
        raise JobFailed(
            f"Only {total} usable images; at least {MIN_IMAGES} overlapping photos "
            "(or enough video) are needed"
        )
    if geotagged < MIN_GEOTAGGED:
        raise JobFailed(
            f"Only {geotagged} of the photos have a location; at least {MIN_GEOTAGGED} are needed "
            "to place and scale the map (a phone video has only one location, which can't; "
            "a GoPro's GPS track can)"
        )
    (work / "exif_overrides.json").write_text(json.dumps(overrides))
    (work / "headings.json").write_text(json.dumps(headings))
    (work / "config.yaml").write_text(yaml.safe_dump(opensfm_config(job, frames_total > 0)))
    return total


def photo_locations(
    fixes: dict[str, tuple[float, float, datetime | None, str | None]], job: MapJob
) -> dict[str, tuple[float, float]]:
    """The photos' GPS positions, unless they are plainly stuck: a phone that never updated its
    location stamps every photo with the same place however far you walked, and trusting that
    would pin the whole map to a point. Positions the mobile app read from the phone's GPS at the
    moment of the shot (``device``) are never doubted this way."""
    from_file = {n: f for n, f in fixes.items() if f[3] != "device"}
    times = [t for _, _, t, _ in from_file.values() if t is not None]
    places = {(round(lat, 5), round(lng, 5)) for lat, lng, _, _ in from_file.values()}
    if (
        len(from_file) >= STALE_MIN_PHOTOS
        and len(places) == 1
        and times
        and (max(times) - min(times)).total_seconds() >= STALE_MIN_SPAN_S
    ):
        _append_log(
            job,
            f"{len(from_file)} photos claim the same location over "
            f"{(max(times) - min(times)).total_seconds() / 60:.1f} minutes, "
            "so their GPS looks stuck and was ignored",
        )
        from_file = {}
    kept = {n: f for n, f in fixes.items() if f[3] == "device" or n in from_file}
    return {name: (lat, lng) for name, (lat, lng, _, _) in kept.items()}


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


def near_duplicate(a: Path, b: Path) -> bool:
    """True if two frames are almost the same picture (a camera that has stopped moving)."""
    pair = []
    for path in (a, b):
        with Image.open(path) as img:
            pair.append(np.asarray(img.convert("L").resize((64, 48)), dtype=float))
    return float(np.abs(pair[0] - pair[1]).mean()) < STATIC_FRAME_DIFF


def extract_frames(
    video: Path, out_dir: Path, prefix: str, fps: float, limit: int, duration: float | None = None
) -> list[tuple[str, float]]:
    """Sample frames from a video as JPEGs, keeping the sharpest of several candidates for each
    sampling point (hand-held video is often blurred) and skipping ones that repeat the last.
    Returns (file name, seconds into the video) for each, in order."""
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
        paths = sorted(Path(tmp).glob("c*.jpg"))
        picks = []
        for start in range(0, len(paths), FRAME_CANDIDATES):
            group = range(start, min(start + FRAME_CANDIDATES, len(paths)))
            best = max(group, key=lambda k: sharpness(paths[k]))
            picks.append((paths[best], best / (rate * FRAME_CANDIDATES)))
        names: list[tuple[str, float]] = []
        last = None
        for path, t in picks:
            if len(names) >= limit:
                break
            if last is not None and near_duplicate(last, path):
                continue
            name = f"{prefix}{len(names) + 1:04d}.jpg"
            shutil.move(path, out_dir / name)
            last = out_dir / name
            names.append((name, t))
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


GPS_TRUSTED_SPREAD_M = 20.0  # cameras spread wider than this: GPS fixes the scale well enough
COMPASS_USED_BELOW_M = 15.0  # cameras bunched tighter than this: GPS can't fix the heading


def located_names(work: Path) -> set[str]:
    """File names of the images given a GPS position (the photos with a location)."""
    overrides = json.loads((work / "exif_overrides.json").read_text())
    return {name for name, o in overrides.items() if "gps" in o}


def input_gps_spread(work: Path, reference: tuple[float, float]) -> float:
    """How widely the photos' GPS positions are spread, in metres (0 if there are none)."""
    overrides = json.loads((work / "exif_overrides.json").read_text())
    lat_m, lon_m = geo.metres_per_degree(reference[0])
    points = [
        (
            (o["gps"]["longitude"] - reference[1]) * lon_m,
            (o["gps"]["latitude"] - reference[0]) * lat_m,
            0.0,
        )
        for o in overrides.values()
        if "gps" in o
    ]
    return geo.gps_spread(np.array(points)) if points else 0.0


def load_levelled(job: MapJob, work: Path) -> tuple[geo.Reconstruction, float]:
    """The reconstruction of the piece holding the located photos, stood upright if it was badly
    tilted, and how widely spread the photos' GPS positions were (metres)."""
    rec = geo.load_reconstruction(
        str(work / "undistorted" / "reconstruction.json"),
        str(work / "reference_lla.json"),
        located=located_names(work),
    )
    rec, tilt = geo.level(rec)
    if tilt:
        _append_log(
            job, f"the reconstruction was tilted {tilt:.0f} degrees from upright: levelled it"
        )
    spread = input_gps_spread(work, rec.reference)
    _append_log(job, f"{len(rec.shots)} photos placed; GPS spread {spread:.0f} m")
    db.session.commit()
    return rec, spread


def load_corrected(
    job: MapJob, work: Path
) -> tuple[geo.Reconstruction, tuple[float, float, float]]:
    """The reconstruction with its scale and heading fixed up where GPS alone can't be trusted.

    OpenSfM fits the cameras to the photos' GPS. If the photos were taken from close together
    (people tend to stand in one spot and turn round) that fit says almost nothing about scale or
    direction, and a water butt can come out a few centimetres wide. So: when the cameras are
    bunched, the scale is set from how high the camera was held; and the phone's compass headings,
    if they agree with each other, set the direction."""
    rec = geo.load_reconstruction(
        str(work / "undistorted" / "reconstruction.json"),
        str(work / "reference_lla.json"),
        located=located_names(work),
    )
    rec, tilt = geo.level(rec)
    if tilt:
        _append_log(
            job, f"the reconstruction was tilted {tilt:.0f} degrees from upright: levelled it"
        )
    plane = geo.ground_plane_for(rec)
    spread = input_gps_spread(work, rec.reference)
    _append_log(
        job,
        f"{len(rec.shots)} photos placed; ground plane fitted to {len(rec.points)} points "
        f"(tilt {100 * math.hypot(*plane[:2]):.0f}%)",
    )
    if spread >= GPS_TRUSTED_SPREAD_M:
        _append_log(
            job, f"photos are spread over about {spread:.0f} m: keeping the GPS scale and heading"
        )
        db.session.commit()  # (a later cancel check refreshes the job and would drop unsaved lines)
        return rec, plane
    factor = geo.height_scale(rec, plane, job.camera_height_m)
    heights = geo.camera_heights(rec, plane)
    _append_log(
        job,
        f"photos are within about {spread:.0f} m of each other, too close for GPS to set the "
        f"scale: cameras sit {np.median(heights):.2f} m above the ground in the reconstruction "
        f"but were held about {job.camera_height_m:.1f} m up, so scaling by {factor:.2f}",
    )
    rec = geo.transform(rec, scale=factor)
    headings = (
        json.loads((work / "headings.json").read_text())
        if (work / "headings.json").exists()
        else {}
    )
    fix = geo.compass_yaw(rec, headings) if spread < COMPASS_USED_BELOW_M else None
    if fix:
        yaw, agreement = fix
        _append_log(
            job,
            f"turning the map {math.degrees(yaw):+.0f} degrees to match the phone compass "
            f"(agreement {agreement:.2f})",
        )
        rec = geo.transform(rec, yaw=yaw)
    else:
        _append_log(job, "no usable compass headings: the direction comes from GPS and may be off")
    db.session.commit()
    return rec, geo.ground_plane_for(rec)


def placed_shots(job: MapJob, work: Path) -> tuple[list[Placed], geo.Reconstruction, tuple]:
    rec, plane = load_corrected(job, work)
    if len(rec.shots) < MIN_GEOTAGGED:
        raise JobFailed(
            f"Only {len(rec.shots)} of the images could be placed together; "
            "take more photos that overlap each other and show the same ground"
        )
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


def propose_boundary(job, rec, shots, fence_points, fence_photos, fused, work=None) -> bool:
    """Fit the plot's outline to the fences and posts found and save it as a suggestion."""
    cloud = np.vstack(fence_points) if fence_points else np.zeros((0, 2))
    inside = np.array([s.centre[:2] for s in shots] + [(g.x, g.y) for g in fused])
    if work is not None:  # kept alongside the other files of the run, for diagnosing a bad outline
        (work / "fence_points.json").write_text(
            json.dumps({"fence": cloud.tolist(), "inside": inside.tolist()})
        )
    fit = boundary_fit.fit_boundary(cloud, inside)
    if fit is None:
        _append_log(job, f"{len(cloud)} fence points: not enough to work out the plot's edge")
        return False
    _append_log(
        job,
        f"{len(cloud)} fence points: found {fit.sides_found} of the plot's 4 sides"
        + ("" if fit.complete else " (the rest are guessed from how far the photos reach)"),
    )
    lon, lat = geo.enu_to_lonlat(
        np.array([c[0] for c in fit.corners]), np.array([c[1] for c in fit.corners]), rec.reference
    )
    ring = [[float(a), float(b)] for a, b in zip(lon, lat, strict=True)]
    # Guessed sides make it a rough outline: it is offered, but not ticked by default.
    confidence = {4: 0.85, 3: 0.65}.get(fit.sides_found, 0.35) + min(fit.support, 40) / 800
    db.session.add(
        MapSuggestion(
            allotment_id=job.allotment_id,
            job_id=job.id,
            kind="boundary",
            name="Plot boundary" if fit.sides_found >= 3 else "Plot boundary (rough)",
            geometry={"type": "Polygon", "coordinates": [[*ring, ring[0]]]},
            radius_m=None,
            confidence=round(confidence, 3),
            views=len(fence_photos),
        )
    )
    return True


def apply_compass(
    job: MapJob, rec: geo.Reconstruction, work: Path, spread: float
) -> geo.Reconstruction:
    """Turn the reconstruction to the phones' compass headings when GPS can't give a heading."""
    if spread >= COMPASS_USED_BELOW_M:
        return rec
    path = work / "headings.json"
    headings = json.loads(path.read_text()) if path.exists() else {}
    fix = geo.compass_yaw(rec, headings)
    if not fix:
        _append_log(job, "no usable compass headings: the direction comes from GPS and may be off")
        return rec
    yaw, agreement = fix
    _append_log(
        job,
        f"turning the map {math.degrees(yaw):+.0f} degrees to match the phone compass "
        f"(agreement {agreement:.2f})",
    )
    return geo.transform(rec, yaw=yaw)


def calibrated_ground(job, rec, shots, raws, spread):
    """The reconstruction in metres with a level ground plane under it.

    GPS fixes the scale if the photos are spread far apart. If not (people stand in one spot and
    turn round), the scale comes from how high the camera was held, measured against the ground's
    height *found from the detections* (they agree across photos only at the right height). If
    that can't be decided, the old way: the ground plane through the point cloud."""
    if spread >= GPS_TRUSTED_SPREAD_M:
        _append_log(job, f"photos spread over about {spread:.0f} m: keeping the GPS scale")
        return rec, geo.ground_plane_for(rec)
    found = calibration.calibrate_height(
        shots, raws, job.camera_height_m, max_range=current_app.config["MAPPING_DETECT_MAX_RANGE_M"]
    )
    if found:
        factor = job.camera_height_m / found.height_units
        _append_log(
            job,
            f"detections from different photos agree (to {100 * found.agreement:.0f}%) with the "
            f"cameras {found.height_units:.2f} units above the ground: held about "
            f"{job.camera_height_m:.1f} m up, so scaling by {factor:.2f}",
        )
        scaled_rec = geo.transform(rec, scale=factor)
        return scaled_rec, calibration.level_plane(scaled_rec.shots, job.camera_height_m)
    plane = geo.ground_plane_for(rec)
    factor = geo.height_scale(rec, plane, job.camera_height_m)
    _append_log(
        job,
        "the detections were too few or too inconsistent to measure the ground height, so the "
        f"point cloud was used instead (less reliable): scaling by {factor:.2f}",
    )
    scaled_rec = geo.transform(rec, scale=factor)
    return scaled_rec, geo.ground_plane_for(scaled_rec)


def use_boundary(job, rec, shots, fused):
    """Leave out objects outside the GPX boundary, if the job has one and the photos agree with it.

    Returns the objects to keep and the boundary in metres (None if there is none to use). If most
    photo positions are outside the trace, the trace (or the photos' GPS) is out of place, and it
    must not be used to throw objects away: that is said in the log instead."""
    if not job.boundary:
        return fused, None
    poly = plot_boundary.to_enu(job.boundary, rec.reference)
    check = plot_boundary.check_cameras(poly, [tuple(s.centre[:2]) for s in shots])
    if (warning := check.message()) is not None:
        _append_log(job, f"GPX boundary: {warning}. It was not used to leave objects out")
        return fused, poly
    kept, dropped = plot_boundary.keep_inside(poly, fused)
    _append_log(
        job,
        f"GPX boundary: {len(kept)} objects inside it"
        + (f", left out {len(dropped)} outside it" if dropped else ""),
    )
    return kept, poly


def propose_gpx_boundary(job) -> bool:
    """Offer the GPX trace's outline as the Plot boundary suggestion, ticked by default."""
    db.session.add(
        MapSuggestion(
            allotment_id=job.allotment_id,
            job_id=job.id,
            kind="boundary",
            name="Plot boundary (from GPX)",
            geometry=job.boundary,
            radius_m=None,
            confidence=0.95,
            views=0,
        )
    )
    return True


MAX_SIGHTINGS = 6


def media_id_of(shot_name: str) -> int | None:
    """Photos are written as m<media id>.jpg and video frames as v<media id>_<n>.jpg."""
    m = re.match(r"[mv](\d+)", shot_name)
    return int(m.group(1)) if m else None


def sightings_of(g: detection_geo.FusedObject) -> list[dict]:
    """Where a found object was seen, to show the person reviewing it: the best sighting from each
    photo, highest score first, with its outline (0..1 of the picture)."""
    best: dict[int, detection_geo.Observation] = {}
    for m in g.members:
        media_id = media_id_of(m.shot)
        if media_id is None or not m.outline:
            continue
        if media_id not in best or m.footprint.score > best[media_id].footprint.score:
            best[media_id] = m
    ranked = sorted(best.items(), key=lambda kv: -kv[1].footprint.score)[:MAX_SIGHTINGS]
    return [
        {"media_id": i, "outline": m.outline, "score": round(m.footprint.score, 3)}
        for i, m in ranked
    ]


def detect_objects(job: MapJob, work: Path, detector=None) -> int:
    """Find objects in the placed photos, put them on the ground and save them as suggestions
    to review. Returns how many were found."""
    set_stage(job, "detecting")
    rec, spread = load_levelled(job, work)
    shots = choose_shots(rec.shots, current_app.config["MAPPING_DETECT_MAX_SHOTS"])
    detector = detector or detector_module.get_detector()
    raws: list[calibration.RawDetection] = []
    for n, shot in enumerate(
        shots, start=1
    ):  # 1. look at the photos; keep where things touch the ground
        check_cancelled(job)
        path = work / "undistorted" / "images" / shot.name
        if not path.exists():
            continue
        with Image.open(path) as image:
            found = detector.detect(image)
        for d in found:
            pixels = detection_geo.contact_points(d.mask)
            if pixels is not None:
                t = d.type
                raws.append(
                    calibration.RawDetection(
                        shot.name,
                        t.name,
                        t.kind,
                        t.shape,
                        d.score,
                        pixels * d.scale,
                        t.role,
                        detection_geo.silhouette(d.mask),
                    )
                )
        _append_log(job, f"looked at photo {n} of {len(shots)}: {len(found)} objects")
        db.session.commit()
    (work / "detections.json").write_text(
        json.dumps([{**vars(r), "pixels": r.pixels.tolist()} for r in raws])
    )
    # 2. fix the scale and heading, 3. put everything on the ground
    rec, plane = calibrated_ground(job, rec, shots, raws, spread)
    rec = apply_compass(job, rec, work, spread)
    by_name = {s.name: s for s in rec.shots}
    shots = [by_name[s.name] for s in shots]
    max_range = current_app.config["MAPPING_DETECT_MAX_RANGE_M"]
    observations: list[detection_geo.Observation] = []
    fence_points: list[np.ndarray] = []  # where posts and the foot of fences meet the ground
    fence_photos: set[str] = set()
    for r in raws:
        shot = by_name[r.shot]
        if r.role != "object":
            pts = detection_geo.ground_points_from_pixels(shot, plane, r.pixels, max_range)
            if r.role == "post" and len(pts):
                pts = np.median(pts, axis=0, keepdims=True)
            if len(pts):
                fence_points.append(pts)
                fence_photos.add(r.shot)
            continue
        fp = detection_geo.footprint_from_pixels(shot, plane, r.pixels, r.score, r.shape, max_range)
        if fp:
            observations.append(
                detection_geo.Observation(r.label, r.kind, r.shape, fp, r.shot, r.outline)
            )
    merged = detection_geo.fuse(observations)
    fused = [g for g in merged if detection_geo.worth_keeping(g)]
    _append_log(job, f"{len(merged)} candidates, {len(fused)} kept after dropping likely noise")
    fused, boundary = use_boundary(job, rec, shots, fused)
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
                sightings=sightings_of(g),
            )
        )
    if boundary is not None:
        outline = propose_gpx_boundary(job)
    else:
        outline = propose_boundary(job, rec, shots, fence_points, fence_photos, fused, work)
    job.objects_found = len(fused) + (1 if outline else 0)
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
