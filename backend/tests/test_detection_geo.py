import math

import numpy as np
import pytest
from PIL import Image, ImageDraw
from shapely.geometry import MultiPoint, Polygon

from allotment import detection_geo as dg
from allotment import mapping_geo as geo

CAMERA = geo.Camera(640, 480, 0.8)
FLAT = (0.0, 0.0, 0.0)


def look_at(position, target, camera=CAMERA) -> geo.Shot:
    position, target = np.asarray(position, float), np.asarray(target, float)
    f = target - position
    f /= np.linalg.norm(f)
    right = np.cross(f, [0, 0, 1.0])
    right /= np.linalg.norm(right)
    down = np.cross(f, right)
    rotation = np.array([right, down, f])
    return geo.Shot("s.jpg", rotation, -rotation @ position, camera)


def cylinder(cx, cy, radius, height, n=48):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = np.c_[cx + radius * np.cos(a), cy + radius * np.sin(a)]
    return np.vstack([np.c_[ring, np.zeros(n)], np.c_[ring, np.full(n, height)]])


def box(cx, cy, w, d, height, angle_deg=0.0):
    c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    base = [
        (cx + x * c - y * s, cy + x * s + y * c) for x in (-w / 2, w / 2) for y in (-d / 2, d / 2)
    ]
    return np.array([(x, y, z) for x, y in base for z in (0, height)])


def render_mask(shot: geo.Shot, points: np.ndarray) -> np.ndarray:
    """A convex 3D object's silhouette as a boolean mask (what a perfect detector gives)."""
    px = geo.project_points(shot, points)
    px = px[~np.isnan(px).any(axis=1)]
    hull = MultiPoint([tuple(p) for p in px]).convex_hull
    img = Image.new("L", (shot.camera.width, shot.camera.height), 0)
    if isinstance(hull, Polygon):
        ImageDraw.Draw(img).polygon(list(hull.exterior.coords), fill=1)
    return np.asarray(img, bool)


RING = [
    look_at((7 * math.cos(a), 7 * math.sin(a), 1.6), (0, 0, 0.6))
    for a in np.radians([0, 55, 110, 170, 230, 290])
]
for i, s in enumerate(RING):
    RING[i] = geo.Shot(f"view{i}.jpg", s.rotation, s.translation, s.camera)

OBJECTS = {
    "water butt": ("water", "circle", cylinder(0.5, 0.0, 0.4, 1.0)),
    "shed": ("shed", "rect", box(-2.0, 1.5, 2.0, 1.5, 2.0, 20)),
    "tree": ("tree", "circle", cylinder(2.0, -2.5, 0.3, 3.0)),
}


def observe(shots, objects=OBJECTS):
    out = []
    for shot in shots:
        for label, (kind, shape, pts) in objects.items():
            mask = render_mask(shot, pts)
            fp = dg.footprint_from_mask(shot, FLAT, mask, 0.8, shape)
            if fp:
                out.append(dg.Observation(label, kind, shape, fp, shot.name))
    return out


def test_project_points_inverts_the_rays():
    shot = RING[0]
    point = np.array([[0.3, -0.2, 0.0]])
    px = geo.project_points(shot, point)
    hit = geo.ground_hits(shot, FLAT, px, 100)[0]
    assert np.allclose(hit, point[0], atol=1e-6)
    assert np.isnan(geo.project_points(shot, np.array([[20.0, 0, 1.0]]))).all()  # behind the camera


def test_a_cylinder_seen_from_one_side_is_located_and_sized():
    fp = dg.footprint_from_mask(
        RING[0], FLAT, render_mask(RING[0], OBJECTS["water butt"][2]), 0.9, "circle"
    )
    assert fp is not None
    assert (fp.x, fp.y) == pytest.approx((0.5, 0.0), abs=0.35)
    assert fp.width == pytest.approx(0.8, abs=0.25)
    assert fp.distance == pytest.approx(6.1, abs=0.5)


def test_several_views_recover_each_object():
    fused = dg.fuse(observe(RING))
    by_label = {g.label: g for g in fused}
    assert set(by_label) == {"water butt", "shed", "tree"}  # one object each, nothing duplicated
    butt, shed, tree = by_label["water butt"], by_label["shed"], by_label["tree"]
    assert (butt.x, butt.y) == pytest.approx((0.5, 0.0), abs=0.25)
    assert butt.width == pytest.approx(0.8, abs=0.2)
    assert (tree.x, tree.y) == pytest.approx((2.0, -2.5), abs=0.3)
    assert (shed.x, shed.y) == pytest.approx((-2.0, 1.5), abs=0.6)  # depth is a guess for boxes
    assert shed.width == pytest.approx(2.0, abs=0.9)
    assert all(g.views == 6 for g in fused)  # every photo sees every object here


def test_more_views_means_more_confidence():
    one = dg.fuse(observe(RING[:1]))
    six = dg.fuse(observe(RING))
    assert max(g.confidence for g in six) > max(g.confidence for g in one)
    assert dg.fuse(observe(RING[:1]), min_views=2) == []


def test_two_different_things_in_one_spot_stay_separate():
    both = {
        "water butt": OBJECTS["water butt"],
        "tree": ("tree", "circle", cylinder(0.6, 0.1, 0.4, 1.0)),
    }
    labels = sorted(g.label for g in dg.fuse(observe(RING, both)))
    assert labels == ["tree", "water butt"]


def test_two_separate_objects_of_the_same_kind_are_not_merged():
    pair = {"water butt": OBJECTS["water butt"]}
    obs = observe(RING, pair)
    other = observe(RING, {"water butt": ("water", "circle", cylinder(-3.0, -1.0, 0.4, 1.0))})
    assert len(dg.fuse(obs + other)) == 2


def test_an_object_cut_off_by_the_bottom_of_the_frame_has_no_known_position():
    mask = np.zeros((480, 640), bool)
    mask[200:480, 100:300] = True  # runs off the bottom
    assert dg.contact_points(mask) is None
    mask[:] = False
    assert dg.contact_points(mask) is None  # nothing at all


def test_contact_points_follow_the_lowest_pixel_of_each_column():
    mask = np.zeros((100, 200), bool)
    mask[20:60, 50:150] = True
    pts = dg.contact_points(mask)
    assert pts is not None
    assert np.allclose(pts[:, 1], 59.5)  # centre of the last row of the mask (row 59)
    assert pts[:, 0].min() >= 50 and pts[:, 0].max() <= 150


def test_far_things_and_things_above_the_horizon_are_dropped():
    shot = RING[0]
    far = render_mask(shot, cylinder(-60, 0, 0.5, 1.0))
    assert dg.footprint_from_mask(shot, FLAT, far, 0.9, "circle") is None
    sky = np.zeros((480, 640), bool)
    sky[10:60, 100:300] = True  # the contact line is above the horizon: no ground there
    assert dg.footprint_from_mask(shot, FLAT, sky, 0.9, "circle") is None


def test_a_mask_made_on_a_smaller_copy_of_the_photo_is_scaled_up():
    shot = RING[0]
    full = render_mask(shot, OBJECTS["water butt"][2])
    small = np.asarray(Image.fromarray(full.astype("uint8") * 255).resize((320, 240)), bool)
    a = dg.footprint_from_mask(shot, FLAT, full, 0.9, "circle")
    b = dg.footprint_from_mask(shot, FLAT, small, 0.9, "circle", scale=2.0)
    assert (b.x, b.y) == pytest.approx((a.x, a.y), abs=0.1)


def test_outlines():
    g = dg.FusedObject("water butt", "water", "circle", 1.0, 2.0, 0.8, 0.8, 0.0, 0.7, 3)
    ring = Polygon(dg.outline(g))
    assert ring.area == pytest.approx(math.pi * 0.4**2, rel=0.03)
    assert (ring.centroid.x, ring.centroid.y) == pytest.approx((1.0, 2.0), abs=1e-6)
    r = dg.FusedObject("shed", "shed", "rect", 0.0, 0.0, 2.0, 1.0, math.radians(90), 0.7, 3)
    rect = Polygon(dg.outline(r))
    assert rect.area == pytest.approx(2.0, rel=1e-6)
    xs, ys = rect.exterior.xy
    assert max(ys) - min(ys) == pytest.approx(
        2.0, abs=1e-6
    )  # turned a quarter: the width runs north-south


def test_a_narrow_object_still_gets_enough_contact_points():
    mask = np.zeros((480, 640), bool)
    mask[200:280, 300:330] = True  # 30 pixels wide in a 640-pixel frame
    pts = dg.contact_points(mask)
    assert pts is not None and len(pts) >= dg.MIN_CONTACT_POINTS
    assert pts[:, 0].min() >= 300 and pts[:, 0].max() <= 330
    thin = np.zeros((480, 640), bool)
    thin[200:280, 300:302] = True  # two columns: too little to measure
    assert dg.contact_points(thin) is None


def _fused(label, width, views, confidence, shape="circle"):
    return dg.FusedObject(label, "water", shape, 0, 0, width, width, 0.0, confidence, views)


def test_implausible_sizes_and_lone_weak_detections_are_dropped():
    assert dg.worth_keeping(_fused("Water butt", 0.8, 3, 0.5))
    assert not dg.worth_keeping(
        _fused("Water butt", 4.0, 5, 0.9)
    )  # no water butt is four metres wide
    assert not dg.worth_keeping(_fused("Water butt", 0.1, 5, 0.9))  # nor ten centimetres
    assert not dg.worth_keeping(_fused("Water butt", 0.8, 1, 0.3))  # seen once, not confident
    assert dg.worth_keeping(
        _fused("Water butt", 0.8, 1, 0.6)
    )  # seen once, but the detector was sure
    assert dg.worth_keeping(
        _fused("Something new", 9.0, 2, 0.2)
    )  # unknown types aren't size-checked


def test_far_objects_are_ignored_when_a_range_is_given():
    shot = RING[0]
    mask = render_mask(shot, OBJECTS["water butt"][2])  # about 6 m away
    assert dg.footprint_from_mask(shot, FLAT, mask, 0.9, "circle", max_range=15) is not None
    assert dg.footprint_from_mask(shot, FLAT, mask, 0.9, "circle", max_range=4) is None
