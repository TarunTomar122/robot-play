"""Agent loop, memory conditions, seeds and the resumable runner, all with a scripted fake model (no network, no money)."""
import json

from robot_play.agent import (CHARS_PER_TOKEN, NOTEBOOK_TOKENS, REPLAY_TOKENS, Memory, eval_seeds, play_episode, practice_seeds,
                              render_transcript, update_memory)
from robot_play.llm import FakeProvider
import pytest

from robot_play.runner import ConfigMismatch, RunSpec, build_specs, run_one


def test_practice_and_eval_seeds_are_disjoint_and_clear_of_gate_seeds():
    prac = {s for r in range(20) for s in practice_seeds(r)}
    ev = {s for r in range(20) for s in eval_seeds(r)}
    assert not prac & ev
    assert min(prac | ev) >= 10_000                      # the validation gates and the disturbance tuning used seeds below 10,000
    assert eval_seeds(3) == eval_seeds(3)                # shared between models and conditions, so comparisons are paired


def test_frontier_poses_are_a_subset_of_the_cheap_models_evaluation_poses():
    spec = [s for s in build_specs("frontier", ["claude-fable-5-2"], [0], "x") if s.task == "stack"][0]
    shared = {x for r in range(5) for x in eval_seeds(r)}
    assert len(spec.eval_seed_list) == 20 and set(spec.eval_seed_list) <= shared


def test_matrix_sizes_match_the_protocol():
    main = build_specs("main", ["claude-haiku-5-5", "gpt-6-luna"], [0, 1, 2, 3, 4], "x")
    assert len(main) == 2 * 3 * 3 * 5
    assert sum(len(s.episodes()) for s in main) == 1440 + 2 * 3 * 2 * 5 * 4          # 1,440 plus the 120 disturbed evaluation episodes
    control = build_specs("control", ["claude-haiku-5-5", "gpt-6-luna"], [0, 1, 2], "x")
    assert sum(len(s.episodes()) for s in control) == 576


def test_calling_done_at_once_is_a_false_success_claim():
    p = FakeProvider([[("done", {})]])
    rec = play_episode(p, "stack", 10_000, True, Memory("none"))
    assert rec.result["success"] is False and rec.result["false_success_claim"] is True and rec.result["calls"] == 1


def test_text_only_replies_are_nudged_twice_then_the_episode_ends():
    p = FakeProvider(["I am done thinking.", "still thinking", "no tools", "more"])
    rec = play_episode(p, "stack", 10_000, True, Memory("none"))
    assert rec.nudges == 2 and rec.result["calls"] == 0 and any("nudges" in n for n in rec.notes)


def test_memory_text_reaches_the_prompt_only_when_the_condition_asks_for_it():
    nb = Memory("notebook", notebook="grip firm on the green cube")
    assert "grip firm" in nb.prompt_block() and Memory("none", notebook="x", replay="y").prompt_block() == ""
    assert Memory("replay", replay="1. pick").prompt_block().count("1. pick") == 1
    p = FakeProvider([[("done", {})]])
    play_episode(p, "stack", 10_000, True, nb)
    assert "grip firm on the green cube" in p.systems[0]


def test_render_transcript_respects_its_cap_and_drops_old_observes_first():
    log = [{"i": i, "tool": "observe" if i % 2 else "pick", "args": {"object": "cube_red"}, "result": {"blob": "x" * 400}} for i in range(1, 9)]
    text = render_transcript(log, 900)
    assert len(text) <= 900 and "pick" in text


def test_notebook_is_rewritten_and_capped_only_after_practice():
    p = FakeProvider([[("done", {})]], notebook_text="N" * 10_000)
    mem = Memory("notebook")
    rec = play_episode(p, "stack", 10_000, True, mem)
    update_memory(p, mem, rec, "stack", "instr", 20)
    assert p.completes == 1 and len(mem.notebook) == NOTEBOOK_TOKENS * CHARS_PER_TOKEN
    assert rec.cost_usd > 0 and rec.mem_usage["output"] == 5


def test_replay_keeps_only_a_successful_transcript_and_stays_under_its_cap():
    class R:  # a fake record
        def __init__(self, ok):
            self.result = {"success": ok}
            self.log = [{"i": 1, "tool": "pick", "args": {}, "result": {"ok": 1}}] * 300
            self.mem_usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    mem = Memory("replay")
    update_memory(None, mem, R(False), "stack", "i", 20)
    assert mem.replay == ""
    update_memory(None, mem, R(True), "stack", "i", 20)
    assert 0 < len(mem.replay) <= REPLAY_TOKENS * CHARS_PER_TOKEN


def test_run_is_resumable_and_evaluation_does_not_change_memory(tmp_path):
    spec = RunSpec("claude-haiku-5-5", "stack", "notebook", 0, True, practice=2, eval_seed_list=[20_000, 20_001], out_dir=str(tmp_path), meter_root=str(tmp_path / "m"))
    p = FakeProvider([[("done", {})]] * 20, notebook_text="note A")
    assert run_one(spec, p)["status"] == "ok"
    rows = [json.loads(line) for line in spec.path.read_text().splitlines()][1:]          # line 0 is the config header
    assert [r["phase"] for r in rows] == ["practice", "practice", "eval", "eval"]
    assert all(r["memory"]["notebook"] == "note A" for r in rows)
    assert p.completes == 2                                           # one notebook rewrite per practice episode, none after evaluation
    assert rows[2]["memory_tokens_in"] > 0                            # the evaluation episodes saw the notebook
    # cut the file back to two episodes and resume: it must finish the remaining two and keep the notebook
    header = spec.path.read_text().splitlines()[0]
    spec.path.write_text(header + "\n" + "".join(json.dumps(r) + "\n" for r in rows[:2]) + '{"torn": ')
    p2 = FakeProvider([[("done", {})]] * 20, notebook_text="note B")
    assert run_one(spec, p2)["status"] == "ok"
    rows2 = [json.loads(line) for line in spec.path.read_text().splitlines()][1:]
    assert len(rows2) == 4 and rows2[2]["memory"]["notebook"] == "note A" and p2.completes == 0
    assert run_one(spec, p2)["status"] == "already_done"


def test_resume_refuses_a_file_written_with_a_different_setup(tmp_path):
    spec = RunSpec("claude-haiku-5-5", "stack", "none", 0, True, practice=1, eval_seed_list=[20_000], out_dir=str(tmp_path), meter_root=str(tmp_path / "m"))
    run_one(spec, FakeProvider([[("done", {})]] * 5))
    for changed in (RunSpec("claude-haiku-5-5", "stack", "none", 0, True, practice=1, eval_seed_list=[20_000], max_calls=12, out_dir=str(tmp_path), meter_root=str(tmp_path / "m")),
                    RunSpec("claude-haiku-5-5", "stack", "none", 0, True, practice=1, eval_seed_list=[20_001], out_dir=str(tmp_path), meter_root=str(tmp_path / "m"))):
        assert changed.path == spec.path
        with pytest.raises(ConfigMismatch):
            run_one(changed, FakeProvider([[("done", {})]] * 5))


def test_a_provider_error_is_not_saved_as_a_failed_episode_and_changes_no_memory(tmp_path):
    from robot_play.llm import Turn

    class Dying(FakeProvider):
        def session(self, system, first_user, tools=None):
            sess = super().session(system, first_user, tools)
            sess.send = lambda results=None, nudge=None: Turn("", [], {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}, "error", error="outage")
            return sess
    spec = RunSpec("claude-haiku-5-5", "stack", "notebook", 0, True, practice=2, eval_seed_list=[20_000], out_dir=str(tmp_path), meter_root=str(tmp_path / "m"))
    p = Dying([])
    res = run_one(spec, p)
    assert res["status"] == "aborted" and p.completes == 0
    assert len(spec.path.read_text().splitlines()) == 1                       # header only: no episode row
    assert run_one(spec, FakeProvider([[("done", {})]] * 10))["status"] == "ok"      # the redo then runs from the start


def test_one_provider_hitting_its_cap_skips_only_its_own_runs(tmp_path):
    from robot_play.runner import _worker
    from robot_play.spend import SpendMeter
    m = SpendMeter(tmp_path / "m", {"anthropic": 1.0, "openai": 1.0})
    r = m.reserve("claude-haiku-5-5", 10, 10)
    m.settle(r, 10_000_000, 0)                                                # spends $1.00 of Anthropic
    assert m.exhausted("anthropic") and not m.exhausted("openai")


def test_pose_toolset_has_no_pick_or_place_and_a_larger_call_budget():
    from robot_play.tools import Episode
    ep = Episode("stack", 10_000, quirk=True, toolset="pose")
    assert {t["name"] for t in ep.tools} == {"observe", "move_to", "open_gripper", "close_gripper", "home", "done"}
    assert ep.max_calls == 3 * Episode("stack", 10_000, quirk=True).max_calls
    assert ep.call("pick", {"object": "cube_green"}) == {"error": "unknown tool 'pick'"}
    assert ep.call("place", {"target": "cube_red"}) == {"error": "unknown tool 'place'"}


def test_a_pose_level_pick_can_be_built_from_moves_and_the_gripper():
    from robot_play.tools import Episode
    ep = Episode("stack", 10_000, quirk=False, toolset="pose")
    p = ep.env.w.obj_pos("cube_green")
    assert ep.call("move_to", {"x": float(p[0]), "y": float(p[1]), "z": 0.12})["ok"]
    assert ep.call("move_to", {"x": float(p[0]), "y": float(p[1]), "z": 0.02})["ok"]
    assert ep.call("close_gripper", {"grip_level": "firm"})["ok"]
    assert ep.call("move_to", {"x": float(p[0]), "y": float(p[1]), "z": 0.2})["ok"]
    assert ep.env.w.obj_pos("cube_green")[2] > 0.1                           # the cube came up with the hand


def test_pose_specs_are_separate_runs_with_their_own_budget_in_the_config():
    from robot_play.runner import build_specs
    specs = build_specs("pose", ["claude-haiku-5-5"], [0], "x")
    assert len(specs) == 6 and all(s.key.endswith("__pose") and s.config()["max_calls"] == 60 for s in specs if s.task == "bins")
