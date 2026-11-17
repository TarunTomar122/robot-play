"""PROTOCOL.md v1.10: the generic sentence taken apart under one neutral label."""
from robot_play.agent import Memory
from robot_play.runner import FRAME, GENERIC_HINT, SPLIT_TEXTS, build_specs

NAMES = ("grip_level", "grasp_height", "release_height", "speed")


def test_the_generic_sentence_is_the_frame_plus_the_instruction_plus_the_names():
    assert GENERIC_HINT.startswith(FRAME)
    assert "change the settings" in GENERIC_HINT and all(n in GENERIC_HINT for n in NAMES)


def test_each_split_text_keeps_the_frame_and_has_exactly_the_registered_parts():
    assert all(t.startswith(FRAME) for t in SPLIT_TEXTS.values())
    has_names = {c: all(n in t for n in NAMES) for c, t in SPLIT_TEXTS.items()}
    assert has_names == {"lm_frame": False, "lm_names": True, "lm_instr": False}
    for c in ("lm_frame", "lm_names", "lm_instr"):
        assert not any(n in SPLIT_TEXTS[c] for n in ("firm", "height 0.", "slow")) and "setting" not in SPLIT_TEXTS[c].replace("adjustable settings", "")
    assert "instead of repeating the same call" in SPLIT_TEXTS["lm_instr"] and "repeating" not in SPLIT_TEXTS["lm_names"] and "repeating" not in SPLIT_TEXTS["lm_frame"]


def test_the_label_is_the_neutral_one_of_v1_9():
    blocks = {c: Memory(c, notebook=t).prompt_block() for c, t in SPLIT_TEXTS.items()}
    for c, b in blocks.items():
        assert b.startswith("\n\nNOTES FOR THIS TASK (object positions change between attempts):\n") and b.endswith(SPLIT_TEXTS[c])
        assert "operator" not in b and "HINT" not in b and "more capable" not in b


def test_the_cell_builds_three_arms_per_job_and_seed_without_practice():
    specs = build_specs("wordsplit", ["claude-haiku-5-5"], [20, 21], "runs/x", tasks=["stack"])
    stack = [s for s in specs if s.task == "stack"]
    assert len(specs) == len(stack)
    assert {s.condition for s in stack} == set(SPLIT_TEXTS) and len(stack) == 3 * 2
    assert all(s.practice == 0 and s.borrowed_notebook == SPLIT_TEXTS[s.condition] for s in stack)
