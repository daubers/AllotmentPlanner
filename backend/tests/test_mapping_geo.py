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
