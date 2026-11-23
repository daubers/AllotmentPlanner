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
