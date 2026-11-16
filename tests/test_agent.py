"""Agent loop, memory conditions, seeds and the resumable runner, all with a scripted fake model (no network, no money)."""
import json

from robot_play.agent import (CHARS_PER_TOKEN, NOTEBOOK_TOKENS, REPLAY_TOKENS, Memory, eval_seeds, play_episode, practice_seeds,
                              render_transcript, update_memory)
from robot_play.llm import FakeProvider
from robot_play.runner import RunSpec, build_specs, run_one


def test_practice_and_eval_seeds_are_disjoint_and_clear_of_gate_seeds():
    prac = {s for r in range(20) for s in practice_seeds(r)}
    ev = {s for r in range(20) for s in eval_seeds(r)}
    assert not prac & ev
    assert min(prac | ev) >= 10_000                      # the validation gates and the disturbance tuning used seeds below 10,000
    assert eval_seeds(3) == eval_seeds(3)                # shared between models and conditions, so comparisons are paired


def test_frontier_poses_are_a_subset_of_the_cheap_models_evaluation_poses():
    spec = [s for s in build_specs("frontier", ["claude-fable-5-2"], [0], "x") if s.task == "stack"][0]
    shared = {x for r in range(5) for x in eval_seeds(r)}
    assert len(spec.eval_seed_list) == 10 and set(spec.eval_seed_list) <= shared


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
    rows = [json.loads(line) for line in spec.path.read_text().splitlines()]
    assert [r["phase"] for r in rows] == ["practice", "practice", "eval", "eval"]
    assert all(r["memory"]["notebook"] == "note A" for r in rows)
    assert p.completes == 2                                           # one notebook rewrite per practice episode, none after evaluation
    assert rows[2]["memory_tokens_in"] > 0                            # the evaluation episodes saw the notebook
    # cut the file back to two episodes and resume: it must finish the remaining two and keep the notebook
    spec.path.write_text("".join(json.dumps(r) + "\n" for r in rows[:2]) + '{"torn": ')
    p2 = FakeProvider([[("done", {})]] * 20, notebook_text="note B")
    assert run_one(spec, p2)["status"] == "ok"
    rows2 = [json.loads(line) for line in spec.path.read_text().splitlines()]
    assert len(rows2) == 4 and rows2[2]["memory"]["notebook"] == "note A" and p2.completes == 0
    assert run_one(spec, p2)["status"] == "already_done"
