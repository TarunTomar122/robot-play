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
    assert sum(len(s.episodes()) for s in control) == 576 + 2 * 3 * 2 * 3 * 4         # 576 plus the disturbed evaluation of the control scenes


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
    lines = [json.loads(x) for x in spec.path.read_text().splitlines()]
    assert len(lines) == 2 and "_config" in lines[0] and "_aborted" in lines[1]          # header and the abandoned-attempt line: no episode row
    assert run_one(spec, FakeProvider([[("done", {})]] * 10))["status"] == "ok"      # the redo then runs from the start
    assert any("_aborted" in json.loads(x) for x in spec.path.read_text().splitlines())   # and the abandoned attempt stays on record


def test_a_failed_notebook_rewrite_aborts_the_run_keeps_the_cost_and_is_redone_without_a_stale_notebook(tmp_path):
    spec = RunSpec("claude-haiku-5-5", "stack", "notebook", 0, True, practice=2, eval_seed_list=[20_000], out_dir=str(tmp_path), meter_root=str(tmp_path / "m"))
    bad = FakeProvider([[("done", {})]] * 20, notebook_text="")           # the rewrite comes back empty (failed or cut off)
    res = run_one(spec, bad)
    assert res["status"] == "aborted" and "notebook" in res["note"]
    rows = [json.loads(x) for x in spec.path.read_text().splitlines()]
    assert [("_aborted" in r) for r in rows] == [False, True]             # header, then the abandoned attempt; no episode row
    assert rows[1]["_aborted"]["usd"] > 0                                  # the episode and the rewrite were paid for and stay on record
    ok = FakeProvider([[("done", {})]] * 20, notebook_text="note B")
    assert run_one(spec, ok)["status"] == "ok"
    eps = [json.loads(x) for x in spec.path.read_text().splitlines() if '"result"' in x]
    assert [e["idx"] for e in eps if e["phase"] == "practice"] == [0, 1] and eps[0]["memory"]["notebook"] == "note B"   # redone from the start with an empty notebook


def test_resume_is_bound_to_the_code_revision_unless_a_change_is_declared(tmp_path, monkeypatch):
    import robot_play.runner as R
    spec = RunSpec("claude-haiku-5-5", "stack", "none", 0, True, practice=1, eval_seed_list=[20_000], out_dir=str(tmp_path), meter_root=str(tmp_path / "m"))
    run_one(spec, FakeProvider([[("done", {})]] * 5))
    monkeypatch.setattr(R, "code_hash", lambda: "different0000000")
    with pytest.raises(ConfigMismatch, match="code"):
        run_one(spec, FakeProvider([[("done", {})]] * 5))
    monkeypatch.setenv(R.ALLOW_CODE_CHANGE, "1")
    run_one(spec, FakeProvider([[("done", {})]] * 5))
    cfg = json.loads(spec.path.read_text().splitlines()[0])["_config"]
    assert cfg["code"] == "different0000000" and cfg["code_history"][0]["to"] == "different0000000"        # the declared change is logged in the file


def test_the_matrix_has_the_episode_counts_the_protocol_promises(tmp_path):
    cheap, front = ["claude-haiku-5-5", "gpt-6-luna"], ["claude-fable-5-2", "gpt-6-astra"]
    cells = {"main": build_specs("main", cheap, list(range(10)), "o"), "control": build_specs("control", cheap, list(range(10)), "o"),
             "frontier": build_specs("frontier", front, [0], "o"), "frontier_exp": build_specs("frontier_exp", ["claude-fable-5-2"], list(range(5)), "o"),
             "pose": build_specs("pose", cheap, list(range(3)), "o")}
    counts = {k: sum(len(s.episodes()) for s in v) for k, v in cells.items()}
    assert counts == {"main": 3360, "control": 2400, "frontier": 120, "frontier_exp": 240, "pose": 576}      # 2,880 + 480 disturbed; 1,920 + 480 disturbed; then the other cells
    assert sum(counts.values()) == 6696
    assert len({s.key for s in cells["frontier_exp"]}) == 15 and len({s.run_seed for s in cells["frontier_exp"]}) == 5
    all_specs = [s for v in cells.values() for s in v]
    assert len({(s.out_dir, s.key) for s in all_specs}) == len(all_specs)                                   # no two runs write the same file within a cell
    for s in all_specs:
        seeds = [e["seed"] for e in s.episodes()]
        prac = {e["seed"] for e in s.episodes() if e["phase"] == "practice"}
        ev = {e["seed"] for e in s.episodes() if e["phase"] != "practice"}
        assert not prac & ev and min(seeds) >= 10_000 and max(seeds) < 50_000        # clear of the gates (below 10,000) and of the pilot (50,000 and up)


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


def test_disturbed_evaluation_uses_slip_and_nudge_except_in_the_control_flask_scene():
    def kinds(task, quirk):
        s = RunSpec("claude-haiku-5-5", task, "none", 0, quirk, disturb_eval=True)
        return [e["disturbance"] for e in s.episodes() if e["phase"] == "eval_disturbed"]
    assert kinds("stack", True) == ["slip", "nudge", "slip", "nudge"] and kinds("stack", False) == ["slip", "nudge", "slip", "nudge"]
    assert kinds("flasks", True) == ["slip", "nudge", "slip", "nudge"]
    assert kinds("flasks", False) == ["slip"] * 4                  # the nudge topples a plain cylinder for good (results/disturbance_control.md)


def test_a_cut_off_turn_aborts_the_episode_even_when_it_carries_a_call():
    from robot_play.llm import ToolCall, Turn

    class Cut(FakeProvider):
        def session(self, system, first_user, tools=None):
            sess = super().session(system, first_user, tools)
            sess.send = lambda results=None, nudge=None: Turn("", [ToolCall("c1", "pick", {"object": "cube_re"})], {"input": 5, "output": 6000, "cache_read": 0, "cache_write": 0}, "max_tokens")
            return sess
    rec = play_episode(Cut([]), "stack", 10_000, True, Memory("none"))
    assert rec.aborted and rec.result["calls"] == 0               # the half-written call was not executed


def test_a_refusal_with_a_call_is_recorded_as_a_refusal():
    from robot_play.llm import ToolCall, Turn

    class Refuse(FakeProvider):
        def session(self, system, first_user, tools=None):
            sess = super().session(system, first_user, tools)
            sess.send = lambda results=None, nudge=None: Turn("no", [], {"input": 5, "output": 5, "cache_read": 0, "cache_write": 0}, "refusal")
            return sess
    rec = play_episode(Refuse([]), "stack", 10_000, True, Memory("none"))
    assert rec.refusal and not rec.aborted
