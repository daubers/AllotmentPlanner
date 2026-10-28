"""Generate small real media files for tests."""

import io
import subprocess
from pathlib import Path

from PIL import Image

from allotment.media_meta import have_ffmpeg

HAVE_FFMPEG = have_ffmpeg()


def _dms(value: float) -> tuple[float, float, float]:
    value = abs(value)
    d = int(value)
    m = int((value - d) * 60)
    return float(d), float(m), round((value - d - m / 60) * 3600, 4)


def make_jpeg(
    size=(64, 48),
    taken: str | None = "2026:10:27 14:03:05",
    gps: tuple[float, float] | None = (51.5, -0.12),
    heading: float | None = None,
    orientation: int | None = None,
    offset: str | None = None,
    colour=(60, 140, 60),
) -> bytes:
    img = Image.new("RGB", size, colour)
    exif = Image.Exif()
    if taken:
        exif[0x0132] = taken
        exif.get_ifd(0x8769)[0x9003] = taken
        if offset:
            exif.get_ifd(0x8769)[0x9011] = offset
    if gps:
        lat, lng = gps
        g = exif.get_ifd(0x8825)
        g[1], g[2] = ("N" if lat >= 0 else "S"), _dms(lat)
        g[3], g[4] = ("E" if lng >= 0 else "W"), _dms(lng)
        if heading is not None:
            g[17] = heading
    if orientation:
        exif[0x0112] = orientation
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def make_png(size=(32, 32)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 100, 50)).save(buf, "PNG")
    return buf.getvalue()


def make_video(
    dest: Path,
    seconds: int = 2,
    created: str | None = "2026-10-27T14:03:05Z",
    location: str | None = "+51.5000-000.1200/",
) -> bytes:
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={seconds}:size=160x120:rate=10",
    ]
    if created:
        cmd += ["-metadata", f"creation_time={created}"]
    if location:
        cmd += ["-metadata", f"location={location}"]
    cmd += ["-pix_fmt", "yuv420p", str(dest)]
    subprocess.run(cmd, check=True, timeout=60)
    return dest.read_bytes()
