"""Text from a photo, by an OCR engine that runs on the CPU. The engine sits behind a small
interface so the rest of the code (and its tests) does not depend on which one it is."""

from dataclasses import dataclass
from typing import Protocol

from PIL import Image

SIDE = 2200  # the longest side the photo is scaled to; small print needs the pixels


@dataclass
class TextLine:
    text: str
    confidence: float
    x: float
    y: float
    height: float  # of the line's box, a good sign of how large the type is


class OcrEngine(Protocol):
    def read(self, image: Image.Image) -> list[TextLine]: ...


class RapidOcrEngine:
    """RapidOCR (PaddleOCR models through ONNX Runtime): CPU only, about 3 s a photo here."""

    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR  # only the worker image has it

        self.engine = RapidOCR(det_limit_side_len=SIDE, det_limit_type="max")

    def read(self, image: Image.Image) -> list[TextLine]:
        import numpy as np

        im = image.convert("RGB")
        scale = SIDE / max(im.size)
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        result, _ = self.engine(np.asarray(im))
        lines = []
        for box, text, score in result or []:
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            lines.append(TextLine(text, float(score), min(xs), min(ys), max(ys) - min(ys)))
        return lines


_engine: OcrEngine | None = None


def get_engine() -> OcrEngine:
    """The shared engine, loaded on first use."""
    global _engine
    if _engine is None:
        _engine = RapidOcrEngine()
    return _engine


def quality(lines: list[TextLine]) -> float:
    """How much confident text a read found: the right way up finds far more than sideways."""
    return sum(ln.confidence * len(ln.text) for ln in lines if ln.confidence > 0.6)


def in_reading_order(lines: list[TextLine], band: float = 25) -> str:
    """The lines as text: rows by height, left to right within a row (good enough for parsing)."""
    out, last = [], None
    for ln in sorted(lines, key=lambda ln: (round(ln.y / band), ln.x)):
        row = round(ln.y / band)
        out.append(("\n" if last is not None and row != last else " ") + ln.text)
        last = row
    return "".join(out).strip()
