"""A GPS track read out of a video file, so each frame can be given the place it was filmed.

GoPro cameras record GPS in a GPMF data stream (``gpmd``) alongside the picture: about 18 fixes a
second. Phones keep one location per video and so give nothing here. Other cameras' formats (DJI
subtitle files, Android timed metadata) are not read.
"""

import json
import statistics
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import mapping_geo as geo

MAX_DOP = 5.0  # drop fixes that are less precise than this (dilution of precision)
MIN_FIX = 2  # 2 = 2D fix, 3 = 3D fix
WINDOW_S = 0.5  # a frame's position is the median of fixes this close to its time
MIN_MOVEMENT_M = 5.0  # a track that never leaves a few metres is a camera that stood still


@dataclass(frozen=True)
class Fix:
    t: float  # seconds from the start of the video
    lat: float
    lng: float


def gpmf_fixes(data: bytes, duration: float) -> list[Fix]:
    """Fixes from a GPMF stream, timed by spreading each one-second block over the video."""
    blocks = [_block_fixes(payload) for key, _, _, payload in _entries(data) if key == b"DEVC"]
    if not blocks:
        return []
    span = duration / len(blocks)
    return [
        Fix((i + (j + 0.5) / len(block)) * span, lat, lng)
        for i, block in enumerate(blocks)
        for j, (lat, lng) in enumerate(block)
    ]


def _entries(data: bytes):
    """(key, size, repeat, payload) for each KLV entry at one level of a GPMF stream."""
    i = 0
    while i + 8 <= len(data):
        key, _kind, size, repeat = struct.unpack(">4scBH", data[i : i + 8])
        length = size * repeat
        yield key, size, repeat, data[i + 8 : i + 8 + length]
        i += 8 + (length + 3) // 4 * 4


def _block_fixes(devc: bytes) -> list[tuple[float, float]]:
    """The usable (lat, lng) pairs of one DEVC block, or none if its fix is poor."""
    for key, _, _, strm in _entries(devc):
        if key != b"STRM":
            continue
        fix, dop, scale, samples = 0, 99.0, (), None
        for name, size, repeat, payload in _entries(strm):
            if name == b"GPSF":
                fix = struct.unpack(">I", payload[:4])[0]
            elif name == b"GPSP":
                dop = struct.unpack(">H", payload[:2])[0] / 100
            elif name == b"SCAL" and size == 4:
                scale = struct.unpack(f">{repeat}i", payload)
            elif name == b"GPS5" and size == 20:
                samples = struct.unpack(f">{repeat * 5}i", payload)
        if samples is not None:  # this is the GPS stream
            if len(scale) < 2 or fix < MIN_FIX or dop > MAX_DOP:
                return []
            return [
                (samples[i] / scale[0], samples[i + 1] / scale[1])
                for i in range(0, len(samples), 5)
            ]
    return []


def read_track(video: Path, duration: float | None) -> list[Fix]:
    """The GPS fixes in a video file (empty if it has no telemetry we can read)."""
    index = _gpmd_stream(video)
    if index is None or not duration:
        return []
    try:
        proc = subprocess.run(  # noqa: S603
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(video),
                "-map",
                f"0:{index}",
                "-c",
                "copy",
                "-f",
                "rawvideo",
                "-",
            ],  # fmt: skip
            capture_output=True,
            timeout=300,
            check=True,
        )
        return gpmf_fixes(proc.stdout, duration)
    except (OSError, subprocess.SubprocessError, struct.error):
        return []


def _gpmd_stream(video: Path) -> int | None:
    try:
        proc = subprocess.run(  # noqa: S603
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=index,codec_tag_string",
                "-of",
                "json",
                str(video),
            ],  # fmt: skip
            capture_output=True,
            timeout=60,
            check=True,
        )
        for stream in json.loads(proc.stdout).get("streams", []):
            if stream.get("codec_tag_string") == "gpmd":
                return int(stream["index"])
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return None


def moves(track: list[Fix]) -> bool:
    """True if the camera went somewhere: a track that stayed put would pin every frame together."""
    if len(track) < 2:
        return False
    lat_m, lng_m = geo.metres_per_degree(track[0].lat)
    xy = np.array([(f.lng * lng_m, f.lat * lat_m) for f in track])
    return float(np.ptp(xy, axis=0).max()) >= MIN_MOVEMENT_M


def position_at(track: list[Fix], t: float) -> tuple[float, float] | None:
    """Where the camera was at time ``t``: the median of nearby fixes, or None in a gap."""
    near = [f for f in track if abs(f.t - t) <= WINDOW_S]
    if not near:
        return None
    return statistics.median(f.lat for f in near), statistics.median(f.lng for f in near)
