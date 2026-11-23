"""The kinds of equipment the app knows about, and a little text handling. Pure, no database.

A kind is a label for what something is ("spade"), so a task that needs digging can suggest
whichever spades you own. An item with no kind is "other". Suggestion rules are added to this
module alongside the kinds.
"""

import re

KINDS: dict[str, str] = {
    "spade": "Spade",
    "fork": "Garden fork",
    "hand_fork": "Hand fork",
    "trowel": "Trowel",
    "dibber": "Dibber",
    "rake": "Rake",
    "hoe": "Hoe",
    "watering_can": "Watering can",
    "hose": "Hose",
    "sprayer": "Sprayer",
    "secateurs": "Secateurs",
    "shears": "Shears",
    "loppers": "Loppers",
    "wheelbarrow": "Wheelbarrow",
    "bucket": "Bucket",
    "string_line": "String line",
    "tape_measure": "Tape measure",
    "cloche": "Cloche",
    "fleece": "Fleece",
    "netting": "Netting",
    "canes": "Canes and supports",
    "twine": "Twine",
    "seed_tray": "Seed tray",
    "plant_labels": "Plant labels",
    "gloves": "Gloves",
    "kneeler": "Kneeler",
    "sieve": "Sieve or riddle",
    "mower": "Mower",
    "strimmer": "Strimmer",
}

STATUSES = ("in_service", "out_of_action")
MAX_KEYWORDS = 20


def kind_label(kind: str | None) -> str:
    """ "Spade" for "spade"; "Other" for no kind or one this version does not know."""
    return KINDS.get(kind or "", "Other")


def parse_keywords(text: str | None) -> list[str]:
    """The words or phrases in a comma or line separated list: lower case, trimmed, no repeats."""
    seen: dict[str, None] = {}
    for part in re.split(r"[,\n;]", text or ""):
        word = " ".join(part.lower().split())
        if word:
            seen.setdefault(word, None)
    return list(seen)[:MAX_KEYWORDS]
