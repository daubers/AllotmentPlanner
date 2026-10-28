import struct

from allotment import video_telemetry as vt


def klv(key: bytes, kind: bytes, size: int, repeat: int, payload: bytes) -> bytes:
    body = struct.pack(">4scBH", key, kind, size, repeat) + payload
    return body + b"\0" * (-len(payload) % 4)


def devc(fixes, fix=3, dop=125, scale=(10_000_000, 10_000_000, 1000, 1000, 100)):
    gps = b"".join(
        struct.pack(">5i", round(la * scale[0]), round(lo * scale[1]), 0, 0, 0) for la, lo in fixes
    )
    stream = (
        klv(b"SCAL", b"l", 4, 5, struct.pack(">5i", *scale))
        + klv(b"GPSF", b"L", 4, 1, struct.pack(">I", fix))
        + klv(b"GPSP", b"S", 2, 1, struct.pack(">H", dop))
        + klv(b"GPS5", b"l", 20, len(fixes), gps)
    )
    accel = klv(b"SCAL", b"s", 2, 1, struct.pack(">h", 418)) + klv(b"ACCL", b"s", 6, 1, bytes(6))
    streams = klv(b"STRM", b"\0", 1, len(accel), accel) + klv(
        b"STRM", b"\0", 1, len(stream), stream
    )
    return klv(b"DEVC", b"\0", 1, len(streams), streams)


def test_fixes_are_read_and_spread_over_the_video():
    data = devc([(51.0, -1.0), (51.0001, -1.0)]) + devc([(51.0002, -1.0), (51.0003, -1.0)])
    fixes = vt.gpmf_fixes(data, duration=2.0)
    assert [round(f.t, 2) for f in fixes] == [0.25, 0.75, 1.25, 1.75]
    assert fixes[3].lat == 51.0003 and fixes[0].lng == -1.0


def test_a_poor_or_missing_fix_gives_nothing():
    assert vt.gpmf_fixes(devc([(51.0, -1.0)], fix=0), 1.0) == []
    assert vt.gpmf_fixes(devc([(51.0, -1.0)], dop=900), 1.0) == []
    assert vt.gpmf_fixes(b"", 1.0) == []


def test_position_is_the_median_of_nearby_fixes_and_gaps_are_none():
    track = [vt.Fix(t / 10, 51.0 + t * 1e-6, -1.0) for t in range(10)]
    track[4] = vt.Fix(0.4, 52.0, -1.0)  # one wild fix
    lat, _ = vt.position_at(track, 0.4)
    assert abs(lat - 51.000004) < 1e-5
    assert vt.position_at(track, 5.0) is None


def test_a_track_that_stays_put_does_not_count_as_moving():
    still = [vt.Fix(i, 51.0 + i * 1e-8, -1.0) for i in range(20)]
    walking = [vt.Fix(i, 51.0 + i * 1e-4, -1.0) for i in range(20)]
    assert not vt.moves(still) and vt.moves(walking)
