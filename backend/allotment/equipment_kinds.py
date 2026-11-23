"""The kinds of equipment the app knows about, and a little text handling. Pure, no database.

A kind is a label for what something is ("spade"), so a task that needs digging can suggest
whichever spades you own. An item with no kind is "other". The rules below decide which kinds a
job needs from its wording, the kind of generated task it is and where it is.
"""

import re
from dataclasses import dataclass, field

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


# --- Which kinds a job needs ---------------------------------------------------------------------

# Rules over a task's title and notes: (pattern, kinds in order of use, why). Patterns match whole
# words, so "digest" is not digging. Easy to tune: it is only data.
RULES: list[tuple[re.Pattern[str], tuple[str, ...], str]] = [
    (
        re.compile(
            r"\b(?:dig|digs|digging|dug|double[- ]dig(?:ging)?|trench(?:es|ing)?"
            r"|turn(?:ing)? over)\b"
        ),
        ("spade", "fork"),
        "digging",
    ),
    (
        re.compile(r"\b(?:sow|sows|sowing|sown|seeds?)\b"),
        ("dibber", "seed_tray", "plant_labels"),
        "sowing",
    ),
    (re.compile(r"\bprick(?:ing)?[- ]out\b"), ("dibber", "seed_tray"), "pricking out"),
    (
        re.compile(r"\b(?:plant(?:ing)? out|transplant\w*|planting|plant)\b"),
        ("trowel", "dibber"),
        "planting",
    ),
    (re.compile(r"\b(?:weed|weeds|weeding|hoe|hoeing)\b"), ("hoe", "hand_fork"), "weeding"),
    (
        re.compile(r"\b(?:prune|prunes|pruning|cut back|deadhead\w*|snip)\b"),
        ("secateurs",),
        "pruning",
    ),
    (re.compile(r"\b(?:hedge|hedges|trim|trimming|clip|clipping)\b"), ("shears",), "trimming"),
    (re.compile(r"\b(?:lopping|loppers|branches)\b"), ("loppers",), "cutting branches"),
    (
        re.compile(r"\b(?:water|waters|watering|irrigat\w*|soak|soaking)\b"),
        ("watering_can", "hose"),
        "watering",
    ),
    (re.compile(r"\b(?:spray|spraying)\b"), ("sprayer",), "spraying"),
    (
        re.compile(r"\b(?:mulch\w*|compost|manure|barrow|spread(?:ing)?)\b"),
        ("wheelbarrow", "fork"),
        "moving material",
    ),
    (
        re.compile(r"\b(?:net|netting|cover|covering|fleece|frost|protect\w*|cloche\w*)\b"),
        ("netting", "fleece", "cloche"),
        "protecting crops",
    ),
    (
        re.compile(r"\b(?:stake\w*|support\w*|tie in|tying|canes?|string up)\b"),
        ("canes", "twine"),
        "supporting plants",
    ),
    (
        re.compile(r"\b(?:harvest\w*|pick|picking|lift|lifting)\b"),
        ("bucket", "secateurs", "trowel"),
        "harvesting",
    ),
    (re.compile(r"\b(?:rake|raking|level|levelling|firm)\b"), ("rake",), "raking"),
    (
        re.compile(r"\b(?:measure|measuring|mark(?:ing)? out|string line|line out)\b"),
        ("tape_measure", "string_line"),
        "measuring out",
    ),
    (re.compile(r"\b(?:mow|mowing|lawn)\b"), ("mower",), "mowing"),
    (re.compile(r"\b(?:strim\w*|edging)\b"), ("strimmer",), "strimming"),
    (re.compile(r"\b(?:sieve|sieving|riddle|riddling)\b"), ("sieve",), "sieving"),
    (re.compile(r"\b(?:clear|clearing|tidy|tidying)\b"), ("fork", "rake"), "clearing"),
]

# The kind of generated task, from its suggestion_key ("plan:sow:12", "tray:3:7:prick-out"). These
# are the strongest signal: the key says what the job is, whatever the title says.
SEGMENT_RULES: dict[str, tuple[str, ...]] = {
    "sow": ("dibber", "seed_tray", "plant_labels"),
    "plant": ("trowel", "dibber"),
    "change": ("fork", "rake"),
    "germination": ("seed_tray",),
    "prick-out": ("dibber", "seed_tray"),
    "harden-off": ("cloche", "fleece"),
    "plant-out": ("trowel", "dibber"),
    "thin": ("hand_fork",),
    "harvest": ("bucket", "secateurs"),
}

# Where the job is: a bed is raked and forked, a compost heap needs a fork and a barrow.
FEATURE_RULES: dict[str, tuple[str, ...]] = {
    "bed": ("rake", "fork"),
    "compost": ("fork", "wheelbarrow"),
}

SEGMENT_SCORE, TEXT_SCORE, FEATURE_SCORE = 3, 2, 1
MAX_KINDS = 4  # kinds suggested for one job
MAX_PER_KIND = 3  # of your items of one kind


@dataclass(frozen=True)
class Hit:
    """A kind a job probably needs, how sure we are (higher is surer) and why."""

    kind: str
    score: int
    reasons: tuple[str, ...]


def suggest_kinds(
    title: str = "",
    description: str = "",
    key: str | None = None,
    feature_kind: str | None = None,
) -> list[Hit]:
    """The kinds of equipment a job probably needs, best first (at most MAX_KINDS).

    A generated task's key decides it (its wording is then ignored); otherwise the title and notes
    do, with where the job is adding a little. Ties keep the order the rules list them in.
    """
    scores: dict[str, int] = {}
    reasons: dict[str, list[str]] = {}

    def add(kinds: tuple[str, ...], score: int, why: str) -> None:
        for kind in kinds:
            scores[kind] = scores.get(kind, 0) + score
            if why not in reasons.setdefault(kind, []):
                reasons[kind].append(why)

    known = [part for part in (key or "").split(":") if part in SEGMENT_RULES]
    for part in known:
        add(SEGMENT_RULES[part], SEGMENT_SCORE, part.replace("-", " "))
    if not known:
        # A generated task's key says exactly what the job is; its title and notes are written by
        # the app ("...sown on 3 Mar") and would only add noise. Your own words are different.
        text = f"{title} {description}".lower()
        for pattern, kinds, why in RULES:
            if pattern.search(text):
                add(kinds, TEXT_SCORE, why)
    if feature_kind in FEATURE_RULES:
        add(FEATURE_RULES[feature_kind], FEATURE_SCORE, f"working in a {feature_kind}")
    first_seen = {kind: i for i, kind in enumerate(scores)}  # the order the rules list them in
    ranked = sorted(scores, key=lambda k: (-scores[k], first_seen[k]))
    return [Hit(k, scores[k], tuple(reasons[k])) for k in ranked[:MAX_KINDS]]


@dataclass(frozen=True)
class Item:
    """The parts of an equipment item that matching needs."""

    id: int
    name: str
    kind: str | None = None
    status: str = "in_service"
    keywords: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Match:
    item_id: int
    reason: str


def _says(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def match_items(
    hits: list[Hit],
    items: list[Item],
    title: str = "",
    description: str = "",
    exclude: set[int] | frozenset[int] = frozenset(),
) -> list[Match]:
    """Which of your items to suggest for a job, most relevant first.

    Items whose own "used for" words appear in the job come first, then your items of each kind the
    job probably needs (at most MAX_PER_KIND of a kind). Anything out of action, or already on the
    job (``exclude``), is left out.
    """
    text = f"{title} {description}".lower()
    usable = [i for i in items if i.status == "in_service" and i.id not in exclude]
    out: list[Match] = []
    seen: set[int] = set()
    for item in usable:
        word = next((k for k in item.keywords if _says(text, k)), None)
        if word is not None:
            out.append(Match(item.id, f"used for “{word}”"))
            seen.add(item.id)
    for hit in hits:
        of_kind = [i for i in usable if i.kind == hit.kind and i.id not in seen]
        for item in of_kind[:MAX_PER_KIND]:
            out.append(Match(item.id, hit.reasons[0]))
            seen.add(item.id)
    return out
