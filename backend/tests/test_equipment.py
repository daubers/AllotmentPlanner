from allotment.equipment_kinds import KINDS, STATUSES, kind_label, parse_keywords


def test_every_kind_has_a_key_and_a_label():
    assert len(KINDS) >= 25
    for key, label in KINDS.items():
        assert key == key.lower() and " " not in key
        assert label and label[0].isupper()
    assert {"spade", "dibber", "trowel", "cloche"} <= set(KINDS)


def test_kind_labels():
    assert kind_label("spade") == "Spade"
    assert kind_label("hand_fork") == "Hand fork"
    assert kind_label(None) == "Other"
    assert kind_label("") == "Other"
    assert kind_label("from-a-newer-version") == "Other"


def test_statuses():
    assert STATUSES == ("in_service", "out_of_action")


def test_keywords_are_split_tidied_and_unique():
    assert parse_keywords("Dig, double digging;  TRENCH\nturn over") == [
        "dig",
        "double digging",
        "trench",
        "turn over",
    ]
    assert parse_keywords("dig, Dig,  dig ") == ["dig"]
    assert parse_keywords("  ,, ;\n") == []
    assert parse_keywords("") == [] and parse_keywords(None) == []


def test_keywords_are_capped():
    many = ", ".join(f"word{i}" for i in range(50))
    assert len(parse_keywords(many)) == 20


# --- suggesting kinds and items ------------------------------------------------------------------

import pytest  # noqa: E402

from allotment.equipment_kinds import (  # noqa: E402
    FEATURE_RULES,
    MAX_KINDS,
    MAX_PER_KIND,
    RULES,
    SEGMENT_RULES,
    Item,
    match_items,
    suggest_kinds,
)


def kinds_for(*args, **kw):
    return [h.kind for h in suggest_kinds(*args, **kw)]


def test_every_rule_points_at_known_kinds():
    for _, kinds, why in RULES:
        assert why and set(kinds) <= set(KINDS), why
    for table in (SEGMENT_RULES, FEATURE_RULES):
        for kinds in table.values():
            assert set(kinds) <= set(KINDS)


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Dig the bed", ["spade", "fork"]),
        ("Double digging the new plot", ["spade", "fork"]),
        ("Trench for the beans", ["spade", "fork"]),
        ("Sow carrots", ["dibber", "seed_tray", "plant_labels"]),
        ("Prick out the tomatoes", ["dibber", "seed_tray"]),
        ("Plant out the leeks", ["trowel", "dibber"]),
        ("Weeding the path edge", ["hoe", "hand_fork"]),
        ("Prune the raspberries", ["secateurs"]),
        ("Water the beans", ["watering_can", "hose"]),
        ("Fleece the brassicas against frost", ["netting", "fleece", "cloche"]),
        ("Tie in the sweet peas", ["canes", "twine"]),
        ("Mow the grass", ["mower"]),
    ],
)
def test_wording_suggests_kinds(title, expected):
    assert kinds_for(title) == expected


def test_it_matches_whole_words_only():
    assert kinds_for("Digest the report") == []
    assert kinds_for("Recover the shed roof") == []  # "cover" inside a word
    assert kinds_for("Sowing") == kinds_for("sowing") == kinds_for("SOWING")


def test_notes_count_as_wording():
    assert "spade" in kinds_for("Bed 3", "dig over before planting")


def test_a_generated_tasks_key_beats_a_vague_title():
    assert kinds_for("Job", key="plan:sow:12") == ["dibber", "seed_tray", "plant_labels"]
    assert kinds_for("Do the thing", key="tray:3:7:prick-out") == ["dibber", "seed_tray"]
    assert kinds_for("x", key="planting:9:thin") == ["hand_fork"]
    assert kinds_for("x", key="tray:3:7:harden-off") == ["cloche", "fleece"]


def test_a_known_key_ignores_the_wording_but_an_unknown_one_does_not():
    # the app writes "...sown on 3 Mar" in its own notes; that must not make it a sowing job
    assert kinds_for("Plant out Tomato", "Sown on 3 Mar", key="tray:3:7:plant-out") == [
        "trowel",
        "dibber",
    ]
    assert kinds_for("Water the beans", key="plan:sow:1") == ["dibber", "seed_tray", "plant_labels"]
    # a key that says nothing about the job (a schedule's) leaves the wording to decide
    assert kinds_for("Water the beans", key="series:4:2026-03-01") == ["watering_can", "hose"]
    assert kinds_for("Water the beans", key=None) == ["watering_can", "hose"]


def test_agreeing_signals_rise_to_the_top():
    hits = suggest_kinds("Job", key="tray:1:2:plant-out", feature_kind="bed")
    assert [h.kind for h in hits][:2] == [
        "trowel",
        "dibber",
    ]  # the key, then the bed's little extras
    assert hits[0].score == 3 and hits[0].reasons == ("plant out",)
    both = suggest_kinds("Tidy up", feature_kind="compost")
    assert both[0].score == 3  # clearing and the compost heap both say fork


def test_where_it_is_adds_a_little():
    assert kinds_for("Tidy up", feature_kind="compost") == ["fork", "rake", "wheelbarrow"]
    assert kinds_for("Job", feature_kind="bed") == ["rake", "fork"]
    assert kinds_for("Job", feature_kind="shed") == []


def test_at_most_a_few_kinds_are_suggested():
    busy = "Dig, sow, plant, weed, prune, water, mulch, harvest and stake"
    assert len(suggest_kinds(busy)) == MAX_KINDS


def test_nothing_to_suggest_for_nothing():
    assert suggest_kinds() == [] and suggest_kinds("Think about next year") == []


def item(i, name, kind=None, status="in_service", keywords=()):
    return Item(i, name, kind, status, tuple(keywords))


def test_your_items_of_the_right_kind_are_suggested():
    items = [item(1, "Border spade", "spade"), item(2, "Hose", "hose"), item(3, "Dibber", "dibber")]
    got = match_items(suggest_kinds("Dig the bed"), items, "Dig the bed")
    assert [(m.item_id, m.reason) for m in got] == [(1, "digging")]


def test_a_kind_you_do_not_own_is_simply_skipped():
    assert (
        match_items(suggest_kinds("Sow carrots"), [item(1, "Border spade", "spade")], "Sow carrots")
        == []
    )


def test_your_own_words_come_first_and_match_whole_words():
    items = [
        item(1, "Border spade", "spade"),
        item(2, "Old trenching tool", None, keywords=["dig", "trench"]),
        item(3, "Rake", "rake", keywords=["digestive"]),
    ]
    got = match_items(suggest_kinds("Dig the bed"), items, "Dig the bed")
    assert [(m.item_id, m.reason) for m in got] == [(2, "used for “dig”"), (1, "digging")]


def test_phrases_in_used_for_work():
    items = [item(1, "Barrow", "wheelbarrow", keywords=["move soil"])]
    assert match_items([], items, "Move soil to bed 4")[0].item_id == 1
    assert match_items([], items, "Remove soiled sacks") == []


def test_out_of_action_and_already_attached_items_are_left_out():
    items = [
        item(1, "Broken spade", "spade", status="out_of_action"),
        item(2, "Good spade", "spade"),
        item(3, "Border spade", "spade"),
    ]
    hits = suggest_kinds("Dig")
    assert [m.item_id for m in match_items(hits, items, "Dig")] == [2, 3]
    assert [m.item_id for m in match_items(hits, items, "Dig", exclude={2})] == [3]


def test_only_a_few_of_one_kind_are_suggested():
    items = [item(i, f"Spade {i}", "spade") for i in range(1, 8)]
    got = match_items(suggest_kinds("Dig"), items, "Dig")
    assert [m.item_id for m in got] == [1, 2, 3] and len(got) == MAX_PER_KIND


def test_an_item_is_suggested_once_even_if_two_things_point_at_it():
    items = [item(1, "Spade", "spade", keywords=["dig"])]
    got = match_items(suggest_kinds("Dig the bed"), items, "Dig the bed")
    assert [m.item_id for m in got] == [1]
