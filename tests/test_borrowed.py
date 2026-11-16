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
