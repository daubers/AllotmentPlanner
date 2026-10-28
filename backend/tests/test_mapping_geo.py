import json
import math

import numpy as np
import pytest

from allotment import mapping_geo as geo

REF = (51.0, -1.0)
CAMERA = geo.Camera(4000, 3000, 0.8)


def shot_at(x, y, z, tilt_deg=0.0, camera=CAMERA, name="a.jpg") -> geo.Shot:
    """A camera at (x, y, z) looking north-and-down, ``tilt_deg`` away from straight down."""
    t = math.radians(tilt_deg)
    forward = np.array([0, math.sin(t), -math.cos(t)])
    right = np.array([1.0, 0, 0])
    down = np.cross(forward, right)
    rotation = np.array([right, down, forward])
    centre = np.array([x, y, z], dtype=float)
    return geo.Shot(name, rotation, -rotation @ centre, camera)


FLAT = (0.0, 0.0, 0.0)


def test_rodrigues_quarter_turn_about_z():
    r = geo.rodrigues([0, 0, math.pi / 2])
    assert np.allclose(r @ [1, 0, 0], [0, 1, 0], atol=1e-12)
    assert np.allclose(geo.rodrigues([0, 0, 0]), np.eye(3))


def test_shot_centre_round_trips():
    assert np.allclose(shot_at(3, 4, 5, tilt_deg=30).centre, [3, 4, 5])


def test_nadir_camera_sees_straight_down():
    shot = shot_at(10, 20, 4)
    centre = geo.ground_hits(shot, FLAT, [[1999.5, 1499.5]], max_range=100)[0]
    assert np.allclose(centre, [10, 20, 0], atol=1e-6)
    left = geo.ground_hits(shot, FLAT, [[0, 1499.5]], max_range=100)[0]
    # half the frame width (0.5 of the long side) at focal 0.8 and 4 m up: 2.5 m either side
    assert left[0] == pytest.approx(10 - 2.4994, abs=1e-3)
    assert left[1] == pytest.approx(20, abs=1e-3)


def test_image_up_is_north():
    top = geo.ground_hits(shot_at(0, 0, 4), FLAT, [[1999.5, 0]], max_range=100)[0]
    bottom = geo.ground_hits(shot_at(0, 0, 4), FLAT, [[1999.5, 2999]], max_range=100)[0]
    assert top[1] > 0 > bottom[1]


def test_a_sloped_plane_changes_where_rays_land():
    flat = geo.ground_hits(shot_at(0, 0, 4), FLAT, [[0, 1499.5]], 100)[0]
    sloped = geo.ground_hits(shot_at(0, 0, 4), (0.1, 0.0, 0.0), [[0, 1499.5]], 100)[0]
    assert sloped[2] == pytest.approx(0.1 * sloped[0], abs=1e-9)  # lies on the plane
    assert sloped[0] != pytest.approx(flat[0], abs=1e-3)


def test_rays_above_the_horizon_and_beyond_range_miss():
    shot = shot_at(0, 0, 1.5, tilt_deg=80)  # nearly level: the top of the frame is sky
    hits = geo.ground_hits(shot, FLAT, [[2000, 0], [2000, 2999]], max_range=60)
    assert np.isnan(hits[0]).all()
    assert not np.isnan(hits[1]).any()
    far = geo.ground_hits(shot_at(0, 0, 1.5, tilt_deg=80), FLAT, [[2000, 1500]], max_range=5)
    assert np.isnan(far).all()


def test_camera_below_the_ground_hits_nothing():
    assert np.isnan(geo.ground_hits(shot_at(0, 0, -1), FLAT, [[2000, 1500]], 100)).all()


def test_crop_keeps_a_nadir_photo_whole_and_trims_sky():
    full = geo.ground_crop(shot_at(0, 0, 4), FLAT, max_range=100)
    assert (full.x0, full.y0, full.x1, full.y1) == (0, 0, 4000, 3000)
    tilted = geo.ground_crop(shot_at(0, 0, 1.6, tilt_deg=75), FLAT, max_range=60)
    assert tilted.y0 > 0 and tilted.y1 == 3000
    top_row = geo.ground_hits(
        shot_at(0, 0, 1.6, tilt_deg=75), FLAT, [[0, tilted.y0], [3999, tilted.y0]], 60
    )
    assert not np.isnan(top_row).any()


def test_crop_gives_up_when_almost_nothing_is_ground():
    assert geo.ground_crop(shot_at(0, 0, 1.6, tilt_deg=105), FLAT, max_range=60) is None


def test_gcp_grid_is_georeferenced_around_the_reference():
    shot = shot_at(10, 20, 4)
    crop = geo.ground_crop(shot, FLAT, 100)
    gcps = geo.gcp_grid(shot, FLAT, crop, REF, n=5)
    assert len(gcps) == 25
    assert gcps[0][:2] == (0.0, 0.0) and gcps[-1][:2] == (3999.0, 2999.0)
    lat_m, lon_m = geo.metres_per_degree(REF[0])
    centre = gcps[12]  # middle of a 5x5 grid
    assert centre[2] == pytest.approx(REF[1] + 10 / lon_m, abs=2e-6)
    assert centre[3] == pytest.approx(REF[0] + 20 / lat_m, abs=2e-6)


def test_gcp_pixels_are_relative_to_the_crop():
    shot = shot_at(0, 0, 1.6, tilt_deg=75)
    crop = geo.ground_crop(shot, FLAT, 60)
    gcps = geo.gcp_grid(shot, FLAT, crop, REF)
    assert gcps[0][1] == 0.0 and gcps[-1][1] == crop.height - 1


def test_ground_resolution_and_choice():
    res = geo.ground_resolution(shot_at(0, 0, 4), FLAT, geo.Crop(0, 0, 4000, 3000))
    assert res == pytest.approx(4 / (0.8 * 4000), rel=1e-3)
    assert geo.choose_resolution([0.001, 0.002]) == 0.01
    assert geo.choose_resolution([1.0]) == 0.25
    assert geo.choose_resolution([0.02, 0.03, 0.05]) == 0.03


def test_zoom_for_resolution():
    assert geo.zoom_for_resolution(0.025, 51.0) == 22
    assert geo.zoom_for_resolution(0.1, 51.0) == 20
    assert geo.zoom_for_resolution(0.0001, 51.0) == 22  # capped
    assert geo.zoom_for_resolution(1.0, 51.0) < geo.zoom_for_resolution(0.5, 51.0)


def test_mercator_round_trip_and_pixel_stretch():
    x, y = geo.lonlat_to_mercator(-1.0, 51.0)
    lon, lat = geo.mercator_to_lonlat(x, y)
    assert (float(lon), float(lat)) == pytest.approx((-1.0, 51.0), abs=1e-9)
    assert geo.mercator_pixel_size(0.02, 51.0) == pytest.approx(0.02 / math.cos(math.radians(51)))


def test_local_degrees_are_about_the_right_size():
    lat_m, lon_m = geo.metres_per_degree(51.0)
    assert lat_m == pytest.approx(111_250, rel=1e-3)
    assert lon_m == pytest.approx(70_197, rel=1e-3)  # WGS84 at 51 N


def test_ground_plane_ignores_plants_standing_on_it():
    rng = np.random.default_rng(1)
    xy = rng.uniform(-15, 15, size=(900, 2))
    z = 0.02 * xy[:, 0] + 0.01 * xy[:, 1] + 0.5 + rng.normal(0, 0.01, 900)
    ground = np.c_[xy, z]
    xy2 = rng.uniform(-15, 15, size=(300, 2))
    plants = np.c_[xy2, 0.02 * xy2[:, 0] + 0.01 * xy2[:, 1] + 0.5 + rng.uniform(0.3, 1.5, 300)]
    a, b, c = geo.fit_ground_plane(np.vstack([ground, plants]))
    assert (a, b) == pytest.approx((0.02, 0.01), abs=0.004)
    assert c == pytest.approx(0.5, abs=0.06)


def test_ground_plane_needs_points():
    with pytest.raises(geo.ReconstructionError):
        geo.fit_ground_plane(np.zeros((3, 3)))


def _write(tmp_path, reconstructions, ref=None):
    rec, refp = tmp_path / "reconstruction.json", tmp_path / "reference_lla.json"
    rec.write_text(json.dumps(reconstructions))
    refp.write_text(json.dumps(ref or {"latitude": 51.0, "longitude": -1.0, "altitude": 2.0}))
    return str(rec), str(refp)


def _recon(n_shots, projection="perspective"):
    return {
        "cameras": {
            "c": {"projection_type": projection, "width": 4000, "height": 3000, "focal": 0.8}
        },
        "shots": {
            f"{i}.jpg": {"rotation": [0, 0, 0], "translation": [0, 0, 5], "camera": "c"}
            for i in range(n_shots)
        },
        "points": {"1": {"coordinates": [1, 2, 0.1]}, "2": {"coordinates": [2, 3, 0.2]}},
    }


def test_load_picks_the_biggest_reconstruction(tmp_path):
    result = geo.load_reconstruction(*_write(tmp_path, [_recon(2), _recon(5)]))
    assert len(result.shots) == 5
    assert result.reference == (51.0, -1.0)
    assert result.points.shape == (2, 3)
    assert result.shots[0].camera.focal == 0.8


def test_load_rejects_unusable_input(tmp_path):
    with pytest.raises(geo.ReconstructionError, match="any of the photos"):
        geo.load_reconstruction(*_write(tmp_path, []))
    with pytest.raises(geo.ReconstructionError, match="camera type"):
        geo.load_reconstruction(*_write(tmp_path, [_recon(3, "fisheye")]))


# --- scale and heading when GPS can't fix them ------------------------------------------------


def _ring(n=6, radius=2.0, height=1.5, tilt=75.0):
    """Cameras on a small circle looking outward and a little down: someone turning round."""
    shots = []
    for i in range(n):
        a = 2 * math.pi * i / n
        centre = np.array([radius * math.cos(a), radius * math.sin(a), height])
        look = centre + np.array([math.cos(a), math.sin(a), -math.cos(math.radians(tilt))])
        f = look - centre
        f /= np.linalg.norm(f)
        right = np.cross(f, [0, 0, 1.0])
        right /= np.linalg.norm(right)
        rotation = np.array([right, np.cross(f, right), f])
        shots.append(geo.Shot(f"p{i}.jpg", rotation, -rotation @ centre, CAMERA))
    return shots


def _rec(shots):
    return geo.Reconstruction((51.0, -1.0), shots, np.zeros((0, 3)))


def test_camera_heights_are_measured_from_the_ground_plane():
    rec = _rec(_ring(height=1.5))
    assert geo.camera_heights(rec, FLAT) == pytest.approx([1.5] * 6)
    # a plane rising 10% towards the east lifts the ground under each camera
    heights = geo.camera_heights(rec, (0.1, 0.0, 0.0))
    assert heights[0] == pytest.approx(1.5 - 0.1 * 2.0)


def test_height_scale_fixes_a_reconstruction_that_came_out_five_times_too_big():
    rec = _rec(_ring(height=7.5))  # really held 1.5 m up
    assert geo.height_scale(rec, FLAT, 1.5) == pytest.approx(0.2)
    with pytest.raises(geo.ReconstructionError):
        geo.height_scale(_rec(_ring(height=-1.0)), FLAT, 1.5)


def test_transform_scales_distances_and_keeps_the_picture_consistent():
    rec = _rec(_ring(height=1.5))
    yaw = math.radians(30)
    moved = geo.transform(rec, scale=0.2, yaw=yaw)
    centre = np.mean([s.centre for s in rec.shots], axis=0)
    # the ground (z = 0) is part of the world too: it moves to z = 1.5 * (1 - 0.2) = 1.2
    assert geo.camera_heights(moved, (0.0, 0.0, 1.2)) == pytest.approx([0.3] * 6)
    assert np.mean([s.centre for s in moved.shots], axis=0) == pytest.approx(
        centre
    )  # pivots on the middle
    before = geo.gps_spread(np.array([s.centre for s in rec.shots]))
    after = geo.gps_spread(np.array([s.centre for s in moved.shots]))
    assert after == pytest.approx(0.2 * before)
    # a ground point must still appear at the same pixel once the world is scaled and turned
    turn = np.array(
        [[math.cos(yaw), -math.sin(yaw), 0], [math.sin(yaw), math.cos(yaw), 0], [0, 0, 1]]
    )
    point = np.array([[4.0, 0.3, 0.0]])  # in front of the camera at (2, 0) looking east
    new_point = (point - centre) @ turn.T * 0.2 + centre
    compared = 0
    for old_shot, new_shot in zip(rec.shots, moved.shots, strict=True):
        was = geo.project_points(old_shot, point)
        if np.isnan(was).any():  # behind this camera
            continue
        compared += 1
        assert geo.project_points(new_shot, new_point) == pytest.approx(was, abs=1e-6)
    assert compared >= 1


def test_turning_the_world_changes_where_cameras_point():
    rec = _rec(_ring())
    before = [geo.view_azimuth(s) for s in rec.shots]
    after = [geo.view_azimuth(s) for s in geo.transform(rec, yaw=math.radians(25)).shots]
    assert [(b - a) % 360 for b, a in zip(before, after, strict=True)] == pytest.approx([25.0] * 6)


def test_compass_headings_give_the_turn_needed():
    rec = _rec(_ring())
    truth = 40.0  # the reconstruction is really 40 degrees out
    headings = {s.name: (geo.view_azimuth(s) - truth) % 360 for s in rec.shots}
    yaw, agreement = geo.compass_yaw(rec, headings)
    assert math.degrees(yaw) == pytest.approx(truth, abs=0.01) and agreement == pytest.approx(1.0)
    fixed = geo.transform(rec, yaw=yaw)
    assert [geo.view_azimuth(s) for s in fixed.shots] == pytest.approx(
        [headings[s.name] for s in fixed.shots], abs=0.01
    )


def test_noisy_compass_headings_still_average_out_and_wild_ones_are_refused():
    rng = np.random.default_rng(4)
    shots = _ring(n=12)
    rec = _rec(shots)
    noisy = {s.name: (geo.view_azimuth(s) - 40 + rng.normal(0, 12)) % 360 for s in shots}
    yaw, agreement = geo.compass_yaw(rec, noisy)
    assert math.degrees(yaw) == pytest.approx(40, abs=8) and 0.9 < agreement <= 1.0
    random_headings = {s.name: float(rng.uniform(0, 360)) for s in shots}
    assert geo.compass_yaw(rec, random_headings) is None  # no agreement: don't turn anything
    assert geo.compass_yaw(rec, {shots[0].name: 10.0}) is None  # too few photos with a heading
    assert geo.compass_yaw(rec, {}) is None


def test_gps_spread_distinguishes_standing_still_from_walking_about():
    standing = np.array([[0, 0, 0], [1.5, 0, 0], [0, 2.0, 0], [-1.0, -1.0, 0]], float)
    walking = standing * 20
    assert geo.gps_spread(standing) < 2.0 < 20.0 < geo.gps_spread(walking)
    assert geo.gps_spread(np.zeros((0, 3))) == 0.0
