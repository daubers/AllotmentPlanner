"""Geometry for turning an OpenSfM reconstruction into a georeferenced orthophoto.

OpenSfM gives every photo a camera pose in a local east/north/up frame (metres) anchored at
``reference_lla``. An allotment is close to flat, so the ground is modelled as a plane fitted to
the reconstructed points; each photo's pixels are cast onto that plane and the result is handed
to GDAL as ground control points. Everything here is plain numpy so it can be tested without
OpenSfM or GDAL installed.

Conventions (OpenSfM): ``x_cam = R @ X + t``; the camera looks along +z with x right and y down;
normalised coordinates are pixels divided by ``max(width, height)`` with the origin at the image
centre, so ``pixel = u * size + width / 2 - 0.5``.
"""

import json
import math
from dataclasses import dataclass

import numpy as np

EARTH_RADIUS = 6378137.0  # Web Mercator's sphere
MIN_CROP_FRACTION = 0.25  # ignore a photo if less than this share of its height sees the ground


class ReconstructionError(Exception):
    """The reconstruction can't be used (message is shown to the user)."""


@dataclass(frozen=True)
class Camera:
    width: int
    height: int
    focal: float  # normalised by max(width, height)

    @property
    def size(self) -> int:
        return max(self.width, self.height)


@dataclass(frozen=True)
class Shot:
    name: str
    rotation: np.ndarray  # 3x3, world -> camera
    translation: np.ndarray  # 3
    camera: Camera

    @property
    def centre(self) -> np.ndarray:
        """Camera position in the world frame."""
        return -self.rotation.T @ self.translation


@dataclass(frozen=True)
class Reconstruction:
    reference: tuple[float, float]  # latitude, longitude of the local frame's origin
    shots: list[Shot]
    points: np.ndarray  # (N, 3) world coordinates


def rodrigues(rvec) -> np.ndarray:
    """Axis-angle vector to rotation matrix."""
    rvec = np.asarray(rvec, dtype=float)
    theta = float(np.linalg.norm(rvec))
    if theta < 1e-12:
        return np.eye(3)
    k = rvec / theta
    kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(theta) * kx + (1 - math.cos(theta)) * (kx @ kx)


def load_reconstruction(
    reconstruction_json: str,
    reference_json: str,
    located: set[str] | None = None,
    min_located: int = 3,
) -> Reconstruction:
    """One reconstruction from OpenSfM's output, with perspective cameras.

    OpenSfM often returns several separate pieces. Only a piece containing located photos
    (``located`` is the set of their file names) is lined up with the real world: the others have
    an arbitrary "up" and position. So the piece with the most located photos wins, and at least
    ``min_located`` are required; without ``located`` the biggest piece is used."""
    with open(reconstruction_json) as f:
        reconstructions = json.load(f)
    with open(reference_json) as f:
        ref = json.load(f)
    if not reconstructions:
        raise ReconstructionError("OpenSfM could not reconstruct any of the photos")
    if located is None:
        best = max(reconstructions, key=lambda r: len(r.get("shots", {})))
    else:
        best = max(
            reconstructions,
            key=lambda r: (len(located & set(r.get("shots", {}))), len(r.get("shots", {}))),
        )
        n = len(located & set(best.get("shots", {})))
        if n < min_located:
            raise ReconstructionError(
                f"Only {n} of the photos with a location could be linked together; at least "
                f"{min_located} are needed to place the map. Take photos that overlap each other "
                "and show the same ground"
            )
    cameras = {}
    for cid, c in best["cameras"].items():
        if c.get("projection_type") != "perspective":
            raise ReconstructionError(
                f"Unsupported camera type after undistortion: {c.get('projection_type')}"
            )
        cameras[cid] = Camera(int(c["width"]), int(c["height"]), float(c["focal"]))
    shots = [
        Shot(
            name,
            rodrigues(s["rotation"]),
            np.array(s["translation"], dtype=float),
            cameras[s["camera"]],
        )
        for name, s in best["shots"].items()
    ]
    points = np.array(
        [p["coordinates"] for p in best.get("points", {}).values()], dtype=float
    ).reshape(-1, 3)
    return Reconstruction((float(ref["latitude"]), float(ref["longitude"])), shots, points)


# --- ground plane ---------------------------------------------------------------------------


def fit_ground_plane(points: np.ndarray, iterations: int = 4) -> tuple[float, float, float]:
    """Plane ``z = a*x + b*y + c`` through the lower part of the point cloud.

    Plants, sheds and fences stick up out of the ground, so after each least-squares fit the
    points well above the plane are dropped and it is fitted again.
    """
    if len(points) < 10:
        raise ReconstructionError("Too few reconstructed points to find the ground")
    pts = points
    a = b = 0.0
    c = float(np.percentile(points[:, 2], 30))
    keep = np.ones(len(pts), dtype=bool)
    for _ in range(iterations):
        design = np.c_[pts[keep, 0], pts[keep, 1], np.ones(keep.sum())]
        a, b, c = np.linalg.lstsq(design, pts[keep, 2], rcond=None)[0]
        residual = pts[:, 2] - (a * pts[:, 0] + b * pts[:, 1] + c)
        spread = max(float(np.median(np.abs(residual[keep]))) * 1.4826, 0.02)
        keep = residual < 1.0 * spread  # drop everything above the ground
        if keep.sum() < 10:
            break
    return float(a), float(b), float(c)


# --- projecting photos onto the ground -------------------------------------------------------


def pixel_rays(shot: Shot, pixels: np.ndarray) -> np.ndarray:
    """World-frame direction of the ray through each (px, py) pixel; shape (N, 3)."""
    cam = shot.camera
    u = (pixels[:, 0] - cam.width / 2.0 + 0.5) / cam.size
    v = (pixels[:, 1] - cam.height / 2.0 + 0.5) / cam.size
    in_camera = np.c_[u / cam.focal, v / cam.focal, np.ones(len(pixels))]
    return in_camera @ shot.rotation  # rows of R^T d  ==  (R^T @ d)^T


def project_points(shot: Shot, points: np.ndarray) -> np.ndarray:
    """Pixels (N, 2) where world points (N, 3) appear; NaN for points behind the camera."""
    cam = shot.camera
    x = np.asarray(points, dtype=float) @ shot.rotation.T + shot.translation
    with np.errstate(divide="ignore", invalid="ignore"):
        u, v = x[:, 0] / x[:, 2] * cam.focal, x[:, 1] / x[:, 2] * cam.focal
    px = np.c_[u * cam.size + cam.width / 2 - 0.5, v * cam.size + cam.height / 2 - 0.5]
    px[x[:, 2] <= 0] = np.nan
    return px


def ground_hits(
    shot: Shot, plane: tuple[float, float, float], pixels, max_range: float
) -> np.ndarray:
    """Where each pixel's ray meets the ground plane: (N, 3) world points, NaN if it doesn't
    (looking above the horizon, or further than ``max_range`` metres away)."""
    a, b, c = plane
    pixels = np.asarray(pixels, dtype=float)
    d = pixel_rays(shot, pixels)
    o = shot.centre
    denom = d[:, 2] - a * d[:, 0] - b * d[:, 1]
    height = o[2] - a * o[0] - b * o[1] - c  # camera height above the plane
    with np.errstate(divide="ignore", invalid="ignore"):
        lam = -height / denom
    hits = o + lam[:, None] * d
    reach = lam * np.linalg.norm(d, axis=1)
    bad = ~np.isfinite(lam) | (lam <= 0) | (reach > max_range) | (height <= 0)
    hits[bad] = np.nan
    return hits


@dataclass(frozen=True)
class Crop:
    """The part of a photo that sees the ground, in photo pixels (x1/y1 exclusive)."""

    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0


def ground_crop(shot: Shot, plane, max_range: float, samples: int = 12) -> Crop | None:
    """Trim the sky (and anything beyond ``max_range``) off the top of a photo.

    Rows are tested from the bottom up; the crop stops at the first row where any sampled column
    no longer reaches the ground. ``None`` if too little of the photo is usable.
    """
    cam = shot.camera
    xs = np.linspace(0, cam.width - 1, samples)
    top = cam.height
    for y in np.linspace(cam.height - 1, 0, samples * 2):
        row = np.c_[xs, np.full(samples, y)]
        if np.isnan(ground_hits(shot, plane, row, max_range)).any():
            break
        top = int(y)
    else:
        top = 0
    if (cam.height - top) < cam.height * MIN_CROP_FRACTION:
        return None
    return Crop(0, top, cam.width, cam.height)


def gcp_grid(
    shot: Shot, plane, crop: Crop, reference, n: int = 5
) -> list[tuple[float, float, float, float]]:
    """``(px, py, lon, lat)`` on an n x n grid over the crop; px/py are relative to the crop."""
    xs = np.linspace(crop.x0, crop.x1 - 1, n)
    ys = np.linspace(crop.y0, crop.y1 - 1, n)
    px = np.array([(x, y) for y in ys for x in xs])
    hits = ground_hits(shot, plane, px, max_range=float("inf"))
    lon, lat = enu_to_lonlat(hits[:, 0], hits[:, 1], reference)
    return [
        (float(p[0] - crop.x0), float(p[1] - crop.y0), float(lo), float(la))
        for p, lo, la in zip(px, lon, lat, strict=True)
    ]


def ground_resolution(shot: Shot, plane, crop: Crop) -> float:
    """Metres of ground per pixel at the middle of the crop."""
    cx, cy = (crop.x0 + crop.x1) / 2, (crop.y0 + crop.y1) / 2
    pair = np.array([[cx, cy], [cx + 1, cy]])
    hits = ground_hits(shot, plane, pair, max_range=float("inf"))
    return float(np.linalg.norm(hits[1] - hits[0]))


def choose_resolution(
    resolutions: list[float], lowest: float = 0.01, highest: float = 0.25
) -> float:
    """Output pixel size in ground metres: the median photo's, within sensible limits."""
    return float(min(max(np.median(resolutions), lowest), highest))


# --- coordinates -----------------------------------------------------------------------------


def metres_per_degree(lat: float) -> tuple[float, float]:
    """(per degree of latitude, per degree of longitude) from the WGS84 series expansion."""
    phi = math.radians(lat)
    lat_m = 111132.92 - 559.82 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)
    lon_m = 111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi)
    return lat_m, lon_m


def enu_to_lonlat(x, y, reference) -> tuple[np.ndarray, np.ndarray]:
    lat0, lon0 = reference
    lat_m, lon_m = metres_per_degree(lat0)
    return lon0 + np.asarray(x) / lon_m, lat0 + np.asarray(y) / lat_m


def lonlat_to_mercator(lon, lat) -> tuple[np.ndarray, np.ndarray]:
    lon, lat = np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)
    x = EARTH_RADIUS * np.radians(lon)
    y = EARTH_RADIUS * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
    return x, y


def mercator_to_lonlat(x, y) -> tuple[np.ndarray, np.ndarray]:
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    return np.degrees(x / EARTH_RADIUS), np.degrees(
        2 * np.arctan(np.exp(y / EARTH_RADIUS)) - np.pi / 2
    )


def mercator_pixel_size(ground_metres: float, lat: float) -> float:
    """Web Mercator units stretch by 1/cos(lat); this is the pixel size that gives
    ``ground_metres`` of real ground per pixel."""
    return ground_metres / math.cos(math.radians(lat))


def zoom_for_resolution(ground_metres: float, lat: float, cap: int = 22) -> int:
    """The XYZ zoom whose pixels are about as coarse as the photos' ground resolution."""
    z = math.log2(2 * math.pi * EARTH_RADIUS * math.cos(math.radians(lat)) / 256 / ground_metres)
    return int(min(cap, max(0, round(z))))


# --- fixing scale and heading when GPS can't ------------------------------------------------------
#
# OpenSfM scales and orients a reconstruction by fitting the camera positions to the photos' GPS.
# That only works if the cameras are spread far more widely than GPS jitter (a few metres). Photos
# taken while standing about in one spot give a scale that can be wrong several times over. Two
# other clues are usually available: how high the camera was held, and the phone's compass.


def camera_heights(rec: Reconstruction, plane: tuple[float, float, float]) -> np.ndarray:
    """Each camera's height above the fitted ground plane, in the reconstruction's units."""
    a, b, c = plane
    return np.array([s.centre[2] - (a * s.centre[0] + b * s.centre[1] + c) for s in rec.shots])


def gps_spread(positions: np.ndarray) -> float:
    """Root-mean-square distance of camera positions from their centre (east/north only)."""
    xy = np.asarray(positions, dtype=float)[:, :2]
    return float(np.sqrt(((xy - xy.mean(axis=0)) ** 2).sum(axis=1).mean())) if len(xy) else 0.0


def transform(
    rec: Reconstruction, scale: float = 1.0, yaw: float = 0.0, about=None
) -> Reconstruction:
    """The reconstruction scaled by ``scale`` and turned ``yaw`` radians anticlockwise (seen from
    above) about the point ``about`` (default: the middle of the cameras)."""
    centres = np.array([s.centre for s in rec.shots])
    origin = np.asarray(about if about is not None else centres.mean(axis=0), dtype=float)
    c, s_ = math.cos(yaw), math.sin(yaw)
    turn = np.array([[c, -s_, 0.0], [s_, c, 0.0], [0.0, 0.0, 1.0]])

    def move(points: np.ndarray) -> np.ndarray:
        return (np.atleast_2d(points) - origin) @ turn.T * scale + origin

    shots = []
    for shot in rec.shots:
        new_centre = move(shot.centre)[0]
        rotation = shot.rotation @ turn.T  # the camera turns with the world
        shots.append(Shot(shot.name, rotation, -rotation @ new_centre, shot.camera))
    return Reconstruction(rec.reference, shots, move(rec.points) if len(rec.points) else rec.points)


def height_scale(
    rec: Reconstruction, plane: tuple[float, float, float], stated_height: float
) -> float:
    """The factor that makes the median camera height above the ground equal ``stated_height``."""
    heights = camera_heights(rec, plane)
    heights = heights[heights > 1e-6]
    if len(heights) == 0:
        raise ReconstructionError("The cameras are not above the ground, so the scale can't be set")
    return float(stated_height / np.median(heights))


def view_azimuth(shot: Shot) -> float:
    """Which way a camera points, degrees clockwise from north (the optical axis on the ground)."""
    forward = shot.rotation[2]  # the camera's z axis (its viewing direction) in world coordinates
    return math.degrees(math.atan2(forward[0], forward[1])) % 360


def compass_yaw(
    rec: Reconstruction, headings: dict[str, float], min_photos: int = 4, min_agreement: float = 0.6
):
    """How far to turn the reconstruction (radians, anticlockwise) so its cameras point where the
    phone's compass said. Returns ``(yaw, agreement)`` or None when too few photos have a heading or
    they disagree too much to trust (agreement is 1.0 for perfect, 0 for random)."""
    deltas = []
    for shot in rec.shots:
        if shot.name in headings:
            # compass is clockwise from north; a world turn is anticlockwise, so the sign flips
            deltas.append(math.radians(view_azimuth(shot) - headings[shot.name]))
    if len(deltas) < min_photos:
        return None
    sin, cos = np.mean(np.sin(deltas)), np.mean(np.cos(deltas))
    agreement = float(math.hypot(sin, cos))
    if agreement < min_agreement:
        return None
    return float(math.atan2(sin, cos)), agreement
