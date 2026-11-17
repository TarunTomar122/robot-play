"""PROTOCOL.md v1.15: the two-sided job. One odd cube needs a firm grip, the other breaks under one; which is which is drawn from the seed."""
import pytest

from robot_play.agent import Memory
from robot_play.env import FRAGILE_N, TASKS
from robot_play.runner import MIXED_TEXTS, SPLIT_TEXTS, build_specs
from robot_play.scripted import run_mixed
from robot_play.tools import Episode

SEEDS = (4000, 4001, 4002, 4003, 4004, 4005)


def test_every_catch_layout_has_one_heavy_and_one_fragile_cube_and_the_control_has_none():
    for s in SEEDS:
        meta = Episode("mixed", s, quirk=True).env.meta
        assert {meta["heavy"], meta["fragile"]} == {"cube_green", "cube_blue"}
        assert Episode("mixed", s, quirk=False).env.meta == {"heavy": None, "fragile": None}
    assert {Episode("mixed", s, quirk=True).env.meta["heavy"] for s in range(4000, 4020)} == {"cube_green", "cube_blue"}     # both assignments occur


def test_the_task_text_is_the_stack_text_and_does_not_mention_the_trap():
    assert TASKS["mixed"].instruction == TASKS["stack"].instruction
    assert "fragile" not in TASKS["mixed"].instruction.lower() and "firm" not in TASKS["mixed"].instruction.lower()


def test_a_firm_grip_on_the_fragile_cube_is_refused_with_the_measured_force_and_a_normal_grip_is_not():
    ep = Episode("mixed", 4003, quirk=True)
    frag = ep.env.meta["fragile"]
    r = ep.call("pick", {"object": frag, "grip_level": "firm"})
    assert not r["ok"] and "squeeze limit exceeded" in r["error"] and f"at most {FRAGILE_N} N" in r["error"]
    ep2 = Episode("mixed", 4003, quirk=True)
    assert ep2.call("pick", {"object": ep2.env.meta["fragile"]})["ok"]


def test_the_heavy_cube_slips_out_of_a_normal_grip_without_an_error_message_and_stays_in_a_firm_one():
    ep = Episode("mixed", 4003, quirk=True)
    r = ep.call("pick", {"object": ep.env.meta["heavy"]})
    assert not r["ok"] and "error" not in r                                    # a silent failure, as in the one-sided job
    ep2 = Episode("mixed", 4003, quirk=True)
    assert ep2.call("pick", {"object": ep2.env.meta["heavy"], "grip_level": "firm"})["ok"]


@pytest.mark.parametrize("policy", ["normal", "light", "firm"])
def test_no_fixed_pick_setting_solves_the_catch_scene_but_all_solve_the_control(policy):
    assert sum(run_mixed(s, True, policy)["ok"] for s in SEEDS) == 0
    assert all(run_mixed(s, False, policy)["ok"] for s in SEEDS[:3])


def test_a_player_that_knows_which_cube_is_which_and_the_try_read_switch_procedure_solve_it():
    assert all(run_mixed(s, True, "oracle")["ok"] for s in SEEDS)
    assert sum(run_mixed(s, True, "procedure")["ok"] for s in SEEDS) >= len(SEEDS) - 1


def test_v1_15_cell_plans_seven_runs_per_model_and_seed_with_the_registered_texts():
    specs = build_specs("mixed", ["claude-haiku-5-5", "gpt-6-luna"], [40, 41], "runs/x", max_calls=20)
    assert len(specs) == 2 * 2 * 7 and {s.task for s in specs} == {"mixed"} and len({s.key for s in specs}) == len(specs)
    one = [s for s in specs if s.model == "gpt-6-luna" and s.run_seed == 40]
    assert sorted((s.condition, s.quirk, s.practice) for s in one) == [
        ("lm_firm", True, 0), ("lm_names", True, 0), ("lm_proc", False, 0), ("lm_proc", True, 0), ("none", False, 0), ("none", True, 0), ("notebook", True, 12)]
    assert all(s.borrowed_notebook == MIXED_TEXTS.get(s.condition, "") for s in one if s.condition != "notebook")
    assert MIXED_TEXTS["lm_names"] == SPLIT_TEXTS["lm_names"]


def test_the_two_new_texts_sit_under_the_same_neutral_label_as_the_earlier_ones():
    for c in ("lm_names", "lm_firm", "lm_proc"):
        assert Memory(c, notebook=MIXED_TEXTS[c]).prompt_block().startswith("\n\nNOTES FOR THIS TASK (object positions change between attempts):")


def test_the_procedure_text_names_both_branches_and_the_constant_text_names_only_firm():
    p, f = MIXED_TEXTS["lm_proc"], MIXED_TEXTS["lm_firm"]
    assert "grip_level firm" in p and "squeeze-limit" in p and "default grip_level" in p and "cube_green" not in p and "cube_blue" not in p
    assert f == "Pick every cube with grip_level firm."
