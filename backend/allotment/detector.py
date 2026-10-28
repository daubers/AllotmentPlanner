"""Finds objects in a photo and outlines them. Runs on the mapper worker only.

Grounding DINO finds things from a text description ("water butt. shed. tree."), then SAM draws
an accurate outline inside each box. Both are open models that run on the CPU; they are
downloaded into ``HF_HOME`` the first time they are needed (they are too big to bake into the
image: the registry in front of it limits the size of a single layer).
"""

import os
from dataclasses import dataclass
from typing import Protocol

import numpy as np
import structlog
from PIL import Image

from .detection_labels import MAX_MASK_FRACTION, TYPES, ObjectType, prompt_text, type_for_phrase

log = structlog.get_logger(__name__)

DETECTOR_MODEL = os.environ.get("DETECTOR_MODEL", "IDEA-Research/grounding-dino-tiny")
SEGMENTER_MODEL = os.environ.get("SEGMENTER_MODEL", "facebook/sam-vit-base")
MAX_SIDE = 1024  # the photo is shrunk to this for the models; masks are scaled back up later
DETECTION_THRESHOLD = 0.25  # lower than any type's own minimum; each type then applies its own


@dataclass
class Detection:
    type: ObjectType
    score: float
    mask: np.ndarray  # boolean, at the size the model saw (see ``scale``)
    scale: float  # camera pixels per mask pixel


class Detector(Protocol):
    def detect(self, image: Image.Image) -> list[Detection]: ...


def filter_detections(
    raw: list[tuple[ObjectType, float, np.ndarray]], frame_pixels: int
) -> list[tuple]:
    """Drop what is clearly wrong: below its type's score bar, or covering far too much of the photo
    to be a single object."""
    kept = []
    for t, score, mask in raw:
        if score < t.min_score:
            continue
        if mask.sum() > MAX_MASK_FRACTION * frame_pixels:
            continue
        kept.append((t, score, mask))
    return kept


class TransformersDetector:
    def __init__(self) -> None:
        import torch  # imported here: only the mapper image has it
        from transformers import (
            AutoModelForZeroShotObjectDetection,
            AutoProcessor,
            SamModel,
            SamProcessor,
        )

        self.torch = torch
        log.info("detector_loading", detector=DETECTOR_MODEL, segmenter=SEGMENTER_MODEL)
        self.det_processor = AutoProcessor.from_pretrained(DETECTOR_MODEL)
        self.det_model = AutoModelForZeroShotObjectDetection.from_pretrained(DETECTOR_MODEL).eval()
        self.seg_processor = SamProcessor.from_pretrained(SEGMENTER_MODEL)
        self.seg_model = SamModel.from_pretrained(SEGMENTER_MODEL).eval()
        self.text = prompt_text()

    def detect(self, image: Image.Image) -> list[Detection]:
        torch = self.torch
        full_w = image.width
        small = image.convert("RGB")
        small.thumbnail((MAX_SIDE, MAX_SIDE))
        scale = full_w / small.width
        inputs = self.det_processor(images=small, text=self.text, return_tensors="pt")
        with torch.no_grad():
            out = self.det_model(**inputs)
        target = [small.size[::-1]]
        try:
            result = self.det_processor.post_process_grounded_object_detection(
                out,
                inputs.input_ids,
                threshold=DETECTION_THRESHOLD,
                text_threshold=0.25,
                target_sizes=target,
            )[0]
        except TypeError:  # older transformers named the argument differently
            result = self.det_processor.post_process_grounded_object_detection(
                out,
                inputs.input_ids,
                box_threshold=DETECTION_THRESHOLD,
                text_threshold=0.25,
                target_sizes=target,
            )[0]
        phrases = result.get("text_labels", result.get("labels"))
        picked = [(i, type_for_phrase(phrases[i])) for i in range(len(phrases))]
        picked = [
            (i, t) for i, t in picked if t is not None and float(result["scores"][i]) >= t.min_score
        ]
        if not picked:
            return []
        seg_in = self.seg_processor(
            small,
            input_boxes=[[result["boxes"][i].tolist() for i, _ in picked]],
            return_tensors="pt",
        )
        with torch.no_grad():
            seg_out = self.seg_model(**seg_in, multimask_output=False)
        masks = self.seg_processor.image_processor.post_process_masks(
            seg_out.pred_masks.cpu(),
            seg_in["original_sizes"].cpu(),
            seg_in["reshaped_input_sizes"].cpu(),
        )[0]
        raw = [
            (t, float(result["scores"][i]), masks[n, 0].numpy().astype(bool))
            for n, (i, t) in enumerate(picked)
        ]
        kept = filter_detections(raw, small.width * small.height)
        return [Detection(t, score, mask, scale) for t, score, mask in kept]


_detector: Detector | None = None


def get_detector() -> Detector:
    """The shared detector, loaded on first use (loading takes about a minute)."""
    global _detector
    if _detector is None:
        _detector = TransformersDetector()
    return _detector


__all__ = ["TYPES", "Detection", "Detector", "get_detector", "filter_detections"]
