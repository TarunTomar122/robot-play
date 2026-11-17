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


def test_v1_11_cell_has_a_no_memory_arm_and_seven_texts_per_seed_and_the_nested_texts_are_nested():
    from robot_play.runner import SPLIT2_TEXTS
    specs = build_specs("wordsplit2", ["claude-haiku-5-5"], [30, 31], "runs/x", tasks=["stack"])
    assert len(specs) == (1 + len(SPLIT2_TEXTS)) * 2 and {s.condition for s in specs} == {"none", *SPLIT2_TEXTS}
    assert all(s.practice == 0 and (s.borrowed_notebook == "" if s.condition == "none" else s.borrowed_notebook == SPLIT2_TEXTS[s.condition]) for s in specs)
    assert SPLIT2_TEXTS["lm_generic"] == GENERIC_HINT
    nested_instr, nested_names = SPLIT2_TEXTS["lm_instr_n"], SPLIT2_TEXTS["lm_names2"]
    assert GENERIC_HINT.startswith(FRAME) and "change the settings one at a time instead of repeating the same call" in nested_instr
    assert not any(n in nested_instr for n in NAMES) and all(n in nested_names for n in NAMES) and "change" not in nested_names and "read the message" in nested_names
    for c in ("lm_instr_n", "lm_names2"):
        assert Memory(c, notebook=SPLIT2_TEXTS[c]).prompt_block().startswith("\n\nNOTES FOR THIS TASK")


def test_v1_12_dose_cell_plans_own_notebooks_after_1_3_6_and_on_fresh_seeds_12_practice_episodes():
    specs = build_specs("dose", ["claude-haiku-5-5"], [20, 30], "runs/x", tasks=["stack"])
    got = sorted((s.run_seed, s.practice) for s in specs)
    assert got == [(20, 1), (20, 3), (20, 6), (30, 1), (30, 3), (30, 6), (30, 12)]
    assert all(s.condition == "notebook" and s.borrowed_notebook == "" for s in specs)
    assert len({s.key for s in specs}) == len(specs)


def test_v1_13_second_model_cells_split_the_arms_into_a_room_check_and_four_text_arms():
    none = build_specs("second_none", ["claude-sonnet-5-5"], [30, 31], "runs/x", tasks=["stack"])
    split = build_specs("second_split", ["claude-sonnet-5-5"], [30, 31], "runs/x", tasks=["stack"])
    assert {s.condition for s in none} == {"none"} and len(none) == 2 and all(s.borrowed_notebook == "" and s.practice == 0 for s in none)
    assert {s.condition for s in split} == {"lm_frame", "lm_names", "lm_instr_n", "lm_generic"} and len(split) == 8
    from robot_play.runner import SPLIT2_TEXTS
    assert all(s.borrowed_notebook == SPLIT2_TEXTS[s.condition] for s in split)
