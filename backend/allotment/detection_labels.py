"""What the detector looks for, and how each kind of thing becomes a map shape."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ObjectType:
    name: str  # shown to the person, e.g. "Water butt"
    kind: str  # FeatureKind value
    shape: str  # "circle" or "rect": how its footprint is drawn
    prompts: tuple[str, ...]  # phrases the detector is asked to find
    min_score: float


# Tuned on a real, overgrown plot: "greenhouse" fires on bare ground unless held to a higher bar,
# and a plastic sheet is easily taken for a water butt. People review everything before it counts.
TYPES: tuple[ObjectType, ...] = (
    ObjectType("Water butt", "water", "circle", ("water butt", "barrel", "water tank"), 0.30),
    ObjectType("Tree", "tree", "circle", ("tree",), 0.35),
    ObjectType("Shed", "shed", "rect", ("shed", "garden shed"), 0.28),
    ObjectType("Greenhouse", "shed", "rect", ("greenhouse", "polytunnel"), 0.45),
    ObjectType("Compost bin", "compost", "rect", ("compost bin", "wooden pallet bin"), 0.30),
    ObjectType("Raised bed", "bed", "rect", ("raised bed",), 0.35),
)

# Anything covering more of the photo than this is a misfire (the ground, the sky), not an object.
MAX_MASK_FRACTION = 0.35


def prompt_text(types: tuple[ObjectType, ...] = TYPES) -> str:
    """The text given to the detector: every phrase, each ending in a full stop."""
    return " ".join(f"{p}." for t in types for p in t.prompts)


def type_for_phrase(phrase: str, types: tuple[ObjectType, ...] = TYPES) -> ObjectType | None:
    """The object type a detected phrase belongs to (the longest matching prompt wins)."""
    text = phrase.lower().strip()
    best: tuple[int, ObjectType] | None = None
    for t in types:
        for p in t.prompts:
            if p in text and (best is None or len(p) > best[0]):
                best = (len(p), t)
    return best[1] if best else None
