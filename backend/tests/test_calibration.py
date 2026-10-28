import numpy as np
import pytest

from allotment import calibration as cal
from allotment import detection_geo as dg
from allotment import mapping_geo as geo

from .test_detection_geo import OBJECTS, RING, render_mask

STATED = 1.6  # RING's cameras really are this high


def raws_for(shots, objects=OBJECTS):
    """What the detector would have left behind: each object's foot, in each photo it is in."""
    out = []
    for shot in shots:
        for label, (kind, shape, pts) in objects.items():
            pixels = dg.contact_points(render_mask(shot, pts))
            if pixels is not None:
                out.append(cal.RawDetection(shot.name, label, kind, shape, 0.8, pixels))
    return out


def scaled_shots(factor):
    rec = geo.Reconstruction((51.0, -1.0), list(RING), np.zeros((0, 3)))
    return geo.transform(rec, scale=factor).shots


def test_the_true_height_is_found_when_the_scale_is_right():
    found = cal.calibrate_height(list(RING), raws_for(RING), STATED)
    assert found is not None
    assert found.height_units == pytest.approx(STATED, rel=0.12)
    assert found.agreement > 0.8


@pytest.mark.parametrize("factor", [0.25, 3.0, 5.0])
def test_a_reconstruction_with_the_wrong_scale_gets_its_height_recovered(factor):
    """The real failure: the cloud says the cameras are 0.4 m (or 8 m) up when they were 1.6 m."""
    shots = scaled_shots(factor)
    # the detections were made in the photos, which don't care about the reconstruction's scale
    found = cal.calibrate_height(shots, raws_for(RING), STATED)
    assert found is not None
    assert found.height_units == pytest.approx(STATED * factor, rel=0.15)


def test_too_few_detections_is_not_enough_to_calibrate():
    assert cal.calibrate_height(list(RING), raws_for(RING)[:5], STATED) is None
    assert cal.calibrate_height(list(RING), [], STATED) is None


def test_detections_that_never_agree_give_no_answer():
    rng = np.random.default_rng(0)
    scatter = [
        cal.RawDetection(
            RING[i % 6].name,
            "Water butt",
            "water",
            "circle",
            0.8,
            rng.uniform([50, 250], [590, 440], (10, 2)),
        )
        for i in range(30)
    ]
    assert cal.calibrate_height(list(RING), scatter, STATED) is None


def test_agreement_counts_only_objects_matched_across_photos():
    one_view = dg.fuse([])
    assert one_view == [] and cal.agreement([]) == 0.0
    a = dg.Footprint(0, 0, 0.8, 0.8, 0.0, 5.0, 0.8)
    lone = [dg.Observation("Water butt", "water", "circle", a, "p1.jpg")]
    assert cal.agreement(lone) == 0.0
    pair = lone + [dg.Observation("Water butt", "water", "circle", a, "p2.jpg")]
    assert cal.agreement(pair) == 1.0
