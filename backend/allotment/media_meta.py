"""Pull capture time, GPS position, heading, size and duration out of photos and videos.

Pure functions over files on disk so they can be tested without Flask or storage.
"""

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from functools import lru_cache

from PIL import Image, ImageOps

THUMB_SIZE = 480
EXIF_IFD = 0x8769
GPS_IFD = 0x8825


class UnsupportedMedia(Exception):
    """The file isn't a photo or video we can handle."""


@dataclass
class Meta:
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    taken_at: datetime | None = None
    lat: float | None = None
    lng: float | None = None
    heading: float | None = None


def sniff_kind(head: bytes) -> str:
    """Decide photo/video from the file's magic bytes (never trust the extension or MIME type)."""
    if head.startswith(b"\xff\xd8\xff") or head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "photo"
    if head[:6] in (b"GIF87a", b"GIF89a") or (head[:4] == b"RIFF" and head[8:12] == b"WEBP"):
        return "photo"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1", b"heim", b"heis"):
            raise UnsupportedMedia(
                "HEIC photos aren't supported yet: set the camera to 'Most Compatible' "
                "or share as JPEG"
            )
        return "video"
    if head.startswith(b"\x1a\x45\xdf\xa3"):  # Matroska / WebM
        return "video"
    raise UnsupportedMedia("Unsupported file type: upload a JPEG, PNG, WebP, GIF, MP4, MOV or WebM")


def _dms(value, ref) -> float | None:
    try:
        d, m, s = (float(x) for x in value)
    except (TypeError, ValueError):
        return None
    degrees = d + m / 60 + s / 3600
    return -degrees if ref in ("S", "W", b"S", b"W") else degrees


def _exif_time(exif, ifd) -> datetime | None:
    raw = (
        ifd.get(0x9003) or ifd.get(0x9004) or exif.get(0x0132)
    )  # DateTimeOriginal/Digitized/DateTime
    if not raw:
        return None
    try:
        taken = datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None
    offset = ifd.get(0x9011)  # OffsetTimeOriginal, e.g. "+01:00"
    match = re.fullmatch(r"([+-])(\d\d):(\d\d)", str(offset or ""))
    if match:
        delta = timedelta(hours=int(match[2]), minutes=int(match[3]))
        return taken.replace(tzinfo=timezone(delta if match[1] == "+" else -delta)).astimezone(UTC)
    return taken.replace(tzinfo=UTC)  # no zone recorded: treat the clock time as UTC


def read_photo(path: str) -> Meta:
    try:
        with Image.open(path) as img:
            img.load()
            exif = img.getexif()
            ifd = exif.get_ifd(EXIF_IFD)
            gps = exif.get_ifd(GPS_IFD)
            meta = Meta(taken_at=_exif_time(exif, ifd))
            width, height = img.size
            if exif.get(0x0112, 1) in (5, 6, 7, 8):  # rotated by orientation: report as displayed
                width, height = height, width
            meta.width, meta.height = width, height
    except Exception as exc:  # noqa: BLE001 - Pillow raises many types for corrupt files
        raise UnsupportedMedia(f"Could not read image: {exc}") from exc
    if gps:
        lat = _dms(gps.get(2), gps.get(1))
        lng = _dms(gps.get(4), gps.get(3))
        if lat is not None and lng is not None and -90 <= lat <= 90 and -180 <= lng <= 180:
            meta.lat, meta.lng = lat, lng
        direction = gps.get(17)
        if direction is not None:
            try:
                meta.heading = float(direction) % 360
            except (TypeError, ValueError):
                pass
    return meta


def make_photo_thumbnail(path: str, dest: str) -> None:
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        img.thumbnail((THUMB_SIZE, THUMB_SIZE))
        img.convert("RGB").save(dest, "JPEG", quality=82)


SHARE_MAX_PX = 2560


def make_share_copy(path: str, dest: str) -> None:
    """A web-sized JPEG for posting elsewhere. Re-encoding drops EXIF, so GPS never leaves."""
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        img.thumbnail((SHARE_MAX_PX, SHARE_MAX_PX))
        img.convert("RGB").save(dest, "JPEG", quality=85)


_ISO6709 = re.compile(r"^([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)")


def parse_iso6709(text: str) -> tuple[float, float] | None:
    """'+51.5000-000.1200/' -> (51.5, -0.12): the location tag phones write into videos."""
    match = _ISO6709.match(text or "")
    if not match:
        return None
    lat, lng = float(match[1]), float(match[2])
    return (lat, lng) if -90 <= lat <= 90 and -180 <= lng <= 180 else None


@lru_cache(maxsize=1)
def have_ffmpeg() -> bool:
    """True only if both tools actually run (a binary on PATH can still be broken)."""
    for tool in ("ffmpeg", "ffprobe"):
        try:
            subprocess.run([tool, "-version"], capture_output=True, timeout=10, check=True)
        except (OSError, subprocess.SubprocessError):
            return False
    return True


def read_video(path: str) -> Meta:
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        ).stdout
        info = json.loads(out)
    except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError) as exc:
        raise UnsupportedMedia("Could not read video") from exc
    stream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if stream is None:
        raise UnsupportedMedia("No video stream found")
    fmt = info.get("format", {})
    tags = {k.lower(): v for k, v in {**fmt.get("tags", {}), **stream.get("tags", {})}.items()}
    meta = Meta(width=stream.get("width"), height=stream.get("height"))
    try:
        meta.duration_s = float(fmt.get("duration") or stream.get("duration"))
    except (TypeError, ValueError):
        pass
    created = tags.get("creation_time")
    if created:
        try:
            meta.taken_at = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            pass
    place = tags.get("com.apple.quicktime.location.iso6709") or tags.get("location")
    pos = parse_iso6709(place) if place else None
    if pos:
        meta.lat, meta.lng = pos
    return meta


def make_video_thumbnail(path: str, dest: str, duration_s: float | None) -> None:
    seek = "1" if (duration_s or 0) > 2 else "0"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-ss",
            seek,
            "-i",
            path,
            "-frames:v",
            "1",
            "-vf",
            f"scale='min({THUMB_SIZE},iw)':-2",
            dest,
        ],
        check=True,
        timeout=120,
    )


def extension_for(kind: str, head: bytes) -> str:
    if kind == "video":
        return (
            ".webm"
            if head.startswith(b"\x1a\x45\xdf\xa3")
            else ".mp4"
            if head[8:12] != b"qt  "
            else ".mov"
        )
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if head.startswith(b"\x89PNG"):
        return ".png"
    return ".gif" if head[:3] == b"GIF" else ".webp"
