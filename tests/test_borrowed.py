"""The borrowed-notebook cell (PROTOCOL.md v1.4, exploratory): a cheap model reads a frozen notebook that a stronger model wrote, and never practises or rewrites it."""
import json

from robot_play.llm import FakeProvider
from robot_play.runner import RunSpec, build_specs, frontier_notebook, run_one

FRONT = "claude-fable-5-2"


def _write_frontier_run(tmp_path, task, run_seed, text, finished=True):
    spec = RunSpec(FRONT, task, "notebook", run_seed, True, out_dir=str(tmp_path))
    plan = spec.episodes()
    rows = [{"phase": p["phase"], "idx": p["idx"], "memory": {"notebook": text, "replay": ""}} for p in plan]
    rows = rows if finished else rows[:-1]
    spec.path.write_text(json.dumps({"_config": {"plan": plan}}) + "\n" + "".join(json.dumps(r) + "\n" for r in rows))


def test_the_borrowed_cell_takes_the_final_notebook_of_finished_frontier_runs_only(tmp_path):
    _write_frontier_run(tmp_path, "stack", 0, "use a firm grip", finished=True)
    _write_frontier_run(tmp_path, "stack", 1, "unfinished", finished=False)
    assert frontier_notebook(str(tmp_path), FRONT, "stack", 0) == "use a firm grip"
    assert frontier_notebook(str(tmp_path), FRONT, "stack", 1) == "" and frontier_notebook(str(tmp_path), FRONT, "bins", 0) == ""
    specs = build_specs("borrowed", ["claude-haiku-5-5", "gpt-6-luna"], [0, 1], "o", source_dir=str(tmp_path))
    assert len(specs) == 2 and {s.model for s in specs} == {"claude-haiku-5-5", "gpt-6-luna"}          # only (stack, run seed 0) has a finished source, once per cheap model
    s = specs[0]
    assert s.practice == 0 and s.condition == "borrowed" and len(s.episodes()) == 4 and all(e["phase"] == "eval" for e in s.episodes())
    assert s.episodes()[0]["seed"] == 20_000 and s.config()["borrowed_notebook"] == "use a firm grip"       # same layouts as every other condition of run seed 0


def test_a_borrowed_run_shows_the_notebook_labelled_as_another_assistants_and_never_rewrites_it(tmp_path):
    seen = []

    class Spy(FakeProvider):
        def session(self, system, first_user, tools=None):
            seen.append(system)
            return super().session(system, first_user, tools)
    spec = RunSpec("claude-haiku-5-5", "stack", "borrowed", 0, True, practice=0, borrowed_notebook="Grip firmly before lifting.", out_dir=str(tmp_path), meter_root=str(tmp_path / "m"))
    p = Spy([[("done", {})]] * 8)
    assert run_one(spec, p)["status"] == "ok"
    assert p.completes == 0                                                     # no notebook rewrite call: the memory is frozen
    assert all("more capable assistant" in u and "Grip firmly before lifting." in u and "written by you" not in u for u in seen) and len(seen) == 4
    rows = [json.loads(x) for x in spec.path.read_text().splitlines()][1:]
    assert all(r["condition"] == "borrowed" and r["memory"]["notebook"] == "Grip firmly before lifting." and r["memory_tokens_in"] > 0 for r in rows)
    spec2 = RunSpec("claude-haiku-5-5", "stack", "borrowed", 0, True, practice=0, borrowed_notebook="a different notebook", out_dir=str(tmp_path), meter_root=str(tmp_path / "m"))
    import pytest
    from robot_play.runner import ConfigMismatch
    with pytest.raises(ConfigMismatch):
        run_one(spec2, FakeProvider([]))                                          # a changed notebook is a different run, never resumed


def test_the_wrong_task_control_reads_another_tasks_notebook_and_says_so(tmp_path):
    for t, text in (("stack", "STACK NOTES"), ("bins", "BINS NOTES"), ("flasks", "FLASK NOTES")):
        _write_frontier_run(tmp_path, t, 0, text)
    specs = {s.task: s for s in build_specs("borrowed_other", ["claude-haiku-5-5"], [0], "o", source_dir=str(tmp_path))}
    assert specs["stack"].borrowed_notebook == "BINS NOTES" and specs["bins"].borrowed_notebook == "FLASK NOTES" and specs["flasks"].borrowed_notebook == "STACK NOTES"
    from robot_play.agent import Memory
    block = Memory("borrowed_other", notebook="x").prompt_block()
    assert "DIFFERENT task" in block and "this same task" not in block and "written by you" not in block
    assert len({s.key for s in specs.values()} | {s.key for s in build_specs("borrowed", ["claude-haiku-5-5"], [0], "o", source_dir=str(tmp_path))}) == 6      # separate files from the matching cell


def test_early_notebook_cells_take_the_notebook_as_it_stood_after_one_or_three_practice_episodes(tmp_path):
    spec = RunSpec(FRONT, "stack", "notebook", 0, True, out_dir=str(tmp_path))
    plan = spec.episodes()
    rows = [{"phase": p["phase"], "idx": p["idx"], "memory": {"notebook": f"after {i + 1}", "replay": ""}} for i, p in enumerate(plan)]
    spec.path.write_text(json.dumps({"_config": {"plan": plan}}) + "\n" + "".join(json.dumps(r) + "\n" for r in rows))
    assert frontier_notebook(str(tmp_path), FRONT, "stack", 0, after=1) == "after 1" and frontier_notebook(str(tmp_path), FRONT, "stack", 0, after=3) == "after 3"
    assert frontier_notebook(str(tmp_path), FRONT, "stack", 0, after=len(plan)) == ""                  # an evaluation row is not a practice notebook
    specs = build_specs("borrowed_3", ["claude-haiku-5-5"], [0], "o", source_dir=str(tmp_path))
    assert len(specs) == 1 and specs[0].condition == "borrowed_3" and specs[0].practice == 0 and specs[0].config()["borrowed_notebook"] == "after 3"
    from robot_play.agent import Memory
    assert "more capable assistant" in Memory("borrowed_1", notebook="x").prompt_block() and "DIFFERENT" not in Memory("borrowed_3", notebook="x").prompt_block()
