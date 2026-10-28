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


def load_reconstruction(reconstruction_json: str, reference_json: str) -> Reconstruction:
    """The biggest reconstruction in OpenSfM's (undistorted) output, with perspective cameras."""
    with open(reconstruction_json) as f:
        reconstructions = json.load(f)
    with open(reference_json) as f:
        ref = json.load(f)
    if not reconstructions:
        raise ReconstructionError("OpenSfM could not reconstruct any of the photos")
    best = max(reconstructions, key=lambda r: len(r.get("shots", {})))
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
