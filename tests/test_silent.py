"""PROTOCOL.md v1.16: the two-sided job with silent damage. A firm grip cracks the fragile cube and nothing says so until the final verdict."""
from robot_play.agent import Memory
from robot_play.runner import MIXED_TEXTS, SILENT_TEXTS, SPLIT_TEXTS, build_specs
from robot_play.scripted import run_mixed
from robot_play.tools import Episode

SEEDS = (4000, 4001, 4002, 4003, 4004, 4005)


def test_the_silent_job_has_the_same_layouts_and_assignments_as_the_explicit_job():
    for s in SEEDS:
        a, b = Episode("mixed", s, quirk=True), Episode("mixed_silent", s, quirk=True)
        assert a.env.meta == b.env.meta
        assert [(o.name, o.pos) for o in a.env.w.scene.objects] == [(o.name, o.pos) for o in b.env.w.scene.objects]


def test_a_firm_grip_on_the_fragile_cube_is_accepted_without_a_word_and_the_cube_is_cracked():
    ep = Episode("mixed_silent", 4003, quirk=True)
    frag = ep.env.meta["fragile"]
    r = ep.call("pick", {"object": frag, "grip_level": "firm"})
    assert r["ok"] and "error" not in r and "crack" not in str(r).lower() and "squeeze" not in str(r).lower()
    assert set(r) == set(Episode("mixed_silent", 4003, quirk=True).call("pick", {"object": frag})), "a cracking pick answers with the same fields as a sound one"
    assert frag in ep.env.w.cracked
    assert "crack" not in str(ep.call("observe", {})).lower()


def test_a_normal_grip_on_the_fragile_cube_cracks_nothing_and_the_verdict_names_a_cracked_cube_only_after_done():
    ep = Episode("mixed_silent", 4003, quirk=True)
    assert ep.call("pick", {"object": ep.env.meta["fragile"]})["ok"] and not ep.env.w.cracked
    r = run_mixed(4003, True, "firm", task="mixed_silent")
    assert not r["ok"] and r["detail"].get("cracked") == [r["fragile"]]


def test_no_fixed_setting_solves_the_silent_catch_scene_and_the_control_scene_is_untouched():
    for policy in ("normal", "light", "firm"):
        assert sum(run_mixed(s, True, policy, task="mixed_silent")["ok"] for s in SEEDS) == 0
    assert all(run_mixed(s, False, "firm", task="mixed_silent")["ok"] for s in SEEDS[:3])
    assert "cracked" not in run_mixed(4000, False, "firm", task="mixed_silent")["detail"]


def test_the_oracle_and_the_try_then_switch_procedure_solve_it_and_a_player_that_keeps_the_fix_fails_when_the_heavy_cube_comes_first():
    assert all(run_mixed(s, True, "oracle", task="mixed_silent")["ok"] for s in SEEDS)
    assert sum(run_mixed(s, True, "procedure", task="mixed_silent")["ok"] for s in SEEDS) >= len(SEEDS) - 1
    for s in SEEDS:
        r = run_mixed(s, True, "sticky", task="mixed_silent")
        assert r["ok"] == (r["heavy"] == "cube_blue"), (s, r["heavy"], r["detail"])           # green is picked first: heavy second means the fix is only ever tried on the heavy cube


def test_the_explicit_job_is_unchanged_by_the_silent_flag():
    ep = Episode("mixed", 4003, quirk=True)
    r = ep.call("pick", {"object": ep.env.meta["fragile"], "grip_level": "firm"})
    assert not r["ok"] and "squeeze limit exceeded" in r["error"] and not ep.env.w.cracked


def test_v1_16_cell_plans_five_runs_per_model_and_seed_with_the_silent_texts():
    specs = build_specs("silent", ["claude-haiku-5-5", "gpt-6-luna"], [40, 41], "runs/x")
    assert len(specs) == 2 * 2 * 5 and {s.task for s in specs} == {"mixed_silent"} and len({s.key for s in specs}) == len(specs)
    one = [s for s in specs if s.model == "claude-haiku-5-5" and s.run_seed == 41]
    assert sorted((s.condition, s.practice) for s in one) == [("lm_firm", 0), ("lm_names", 0), ("lm_proc", 0), ("none", 0), ("notebook", 12)]
    assert all(s.quirk for s in specs) and all(s.borrowed_notebook == SILENT_TEXTS.get(s.condition, "") for s in one if s.condition != "notebook")


def test_the_silent_answer_key_differs_from_the_explicit_one_only_where_the_world_does():
    p, q = SILENT_TEXTS["lm_proc"], MIXED_TEXTS["lm_proc"]
    assert "squeeze-limit" not in p and "squeeze-limit" in q and "crack" in p and "only the final verdict shows it" in p
    assert SILENT_TEXTS["lm_names"] == SPLIT_TEXTS["lm_names"] == MIXED_TEXTS["lm_names"] and SILENT_TEXTS["lm_firm"] == MIXED_TEXTS["lm_firm"]
    assert "cube_green" not in p and "cube_blue" not in p
    assert Memory("lm_proc", notebook=p).prompt_block().startswith("\n\nNOTES FOR THIS TASK (object positions change between attempts):")
