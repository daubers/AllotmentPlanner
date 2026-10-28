import pytest
from PIL import Image

from allotment import media_meta as mm

from .helpers import HAVE_FFMPEG, make_jpeg, make_png, make_video


def write(tmp_path, data: bytes, name="f.bin"):
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


def test_sniff_kind_uses_magic_bytes():
    assert mm.sniff_kind(make_jpeg()[:32]) == "photo"
    assert mm.sniff_kind(make_png()[:32]) == "photo"
    assert mm.sniff_kind(b"GIF89a" + b"\0" * 26) == "photo"
    assert mm.sniff_kind(b"RIFF\0\0\0\0WEBPVP8 " + b"\0" * 16) == "photo"
    assert mm.sniff_kind(b"\0\0\0\x18ftypmp42" + b"\0" * 20) == "video"
    assert mm.sniff_kind(b"\0\0\0\x14ftypqt  " + b"\0" * 20) == "video"
    assert mm.sniff_kind(b"\x1a\x45\xdf\xa3" + b"\0" * 28) == "video"


@pytest.mark.parametrize(
    "head", [b"hello world, not media at all....", b"%PDF-1.7" + b"\0" * 24, b""]
)
def test_sniff_rejects_other_files(head):
    with pytest.raises(mm.UnsupportedMedia):
        mm.sniff_kind(head)


def test_sniff_explains_heic():
    with pytest.raises(mm.UnsupportedMedia, match="HEIC"):
        mm.sniff_kind(b"\0\0\0\x18ftypheic" + b"\0" * 20)


def test_reads_exif_time_and_gps(tmp_path):
    meta = mm.read_photo(write(tmp_path, make_jpeg(gps=(51.5, -0.12), heading=90.0)))
    assert (meta.width, meta.height) == (64, 48)
    assert meta.taken_at.isoformat() == "2026-10-27T14:03:05+00:00"
    assert meta.lat == pytest.approx(51.5, abs=1e-4)
    assert meta.lng == pytest.approx(-0.12, abs=1e-4)
    assert meta.heading == 90.0


def test_southern_and_eastern_hemispheres(tmp_path):
    meta = mm.read_photo(write(tmp_path, make_jpeg(gps=(-33.8688, 151.2093))))
    assert meta.lat == pytest.approx(-33.8688, abs=1e-3)
    assert meta.lng == pytest.approx(151.2093, abs=1e-3)


def test_exif_offset_converts_to_utc(tmp_path):
    meta = mm.read_photo(
        write(
            tmp_path, make_jpeg(taken="2026-10-27 14:03:05".replace("-", ":", 2), offset="+01:00")
        )
    )
    assert meta.taken_at.isoformat() == "2026-10-27T13:03:05+00:00"


def test_photo_without_exif(tmp_path):
    meta = mm.read_photo(write(tmp_path, make_png((20, 10))))
    assert (meta.width, meta.height) == (20, 10)
    assert meta.taken_at is None and meta.lat is None and meta.heading is None


def test_orientation_swaps_reported_size(tmp_path):
    meta = mm.read_photo(write(tmp_path, make_jpeg(size=(64, 48), orientation=6)))
    assert (meta.width, meta.height) == (48, 64)


def test_garbage_gps_is_ignored(tmp_path):
    # latitude 95 is impossible: keep the photo, drop the position
    meta = mm.read_photo(write(tmp_path, make_jpeg(gps=(95.0, 10.0))))
    assert meta.lat is None and meta.lng is None


def test_corrupt_image_is_unsupported(tmp_path):
    with pytest.raises(mm.UnsupportedMedia):
        mm.read_photo(write(tmp_path, b"\xff\xd8\xff" + b"garbage" * 20))


def test_thumbnail_is_bounded_and_upright(tmp_path):
    src = write(tmp_path, make_jpeg(size=(1200, 800), orientation=6))
    dest = str(tmp_path / "t.jpg")
    mm.make_photo_thumbnail(src, dest)
    with Image.open(dest) as img:
        assert img.format == "JPEG"
        assert max(img.size) == mm.THUMB_SIZE
        assert img.size[1] > img.size[0]  # rotated upright: portrait


@pytest.mark.parametrize(
    "text,expected",
    [
        ("+51.5000-000.1200/", (51.5, -0.12)),
        ("-33.8688+151.2093+012.000/", (-33.8688, 151.2093)),
        ("+95.0000+010.0000/", None),
        ("nonsense", None),
        ("", None),
    ],
)
def test_iso6709(text, expected):
    assert mm.parse_iso6709(text) == expected


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")
def test_reads_video_metadata_and_thumbnail(tmp_path):
    path = tmp_path / "v.mp4"
    make_video(path)
    meta = mm.read_video(str(path))
    assert (meta.width, meta.height) == (160, 120)
    assert meta.duration_s == pytest.approx(2.0, abs=0.3)
    assert meta.taken_at.isoformat() == "2026-10-27T14:03:05+00:00"
    assert (meta.lat, meta.lng) == (51.5, -0.12)
    thumb = tmp_path / "t.jpg"
    mm.make_video_thumbnail(str(path), str(thumb), meta.duration_s)
    with Image.open(thumb) as img:
        assert img.format == "JPEG" and img.size[0] <= mm.THUMB_SIZE


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")
def test_not_a_video_is_unsupported(tmp_path):
    with pytest.raises(mm.UnsupportedMedia):
        mm.read_video(write(tmp_path, b"\0\0\0\x18ftypmp42" + b"junk" * 50))
