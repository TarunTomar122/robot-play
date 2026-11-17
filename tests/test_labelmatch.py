"""PROTOCOL.md v1.9: the label-matched text control."""
from robot_play.agent import Memory
from robot_play.runner import GENERIC_HINT, HINTS, INERT_TEXT, build_specs


def test_the_three_conditions_share_one_label():
    texts = {"lm_inert": INERT_TEXT, "lm_generic": GENERIC_HINT, "lm_specific": HINTS["stack"]}
    blocks = {c: Memory(c, notebook=t).prompt_block() for c, t in texts.items()}
    assert len({b.split(":\n")[0] for b in blocks.values()}) == 1 and "NOTES FOR THIS TASK" in blocks["lm_inert"]
    for c, b in blocks.items():
        assert b.endswith(texts[c]) and "operator" not in b and "more capable" not in b and "HINT" not in b


def test_the_inert_sentence_names_no_setting_and_matches_the_generic_length():
    for word in ("grip", "grasp", "release", "speed", "firm", "height", "yaw", "lift", "settle"):
        assert word not in INERT_TEXT.lower()
    assert abs(len(INERT_TEXT) - len(GENERIC_HINT)) <= 0.1 * len(GENERIC_HINT)


def test_the_cell_builds_three_conditions_per_job_and_seed_without_practice():
    specs = build_specs("labelmatch", ["claude-haiku-5-5"], [20, 21], "runs/x")
    assert len(specs) == 3 * 3 * 2
    assert {s.condition for s in specs} == {"lm_inert", "lm_generic", "lm_specific"}
    assert all(s.practice == 0 and s.borrowed_notebook for s in specs)
    texts = {(s.task, s.condition): s.borrowed_notebook for s in specs}
    assert texts[("stack", "lm_specific")] == HINTS["stack"] and texts[("bins", "lm_generic")] == GENERIC_HINT and texts[("flasks", "lm_inert")] == INERT_TEXT
