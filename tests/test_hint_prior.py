"""The hint and prior cells of PROTOCOL.md v1.7: no practice, one fixed memory text, the labels the protocol names, and hints that name the fixing setting."""
import json

from robot_play.agent import Memory, prior_request
from robot_play.runner import GENERIC_HINT, HINTS, build_specs, prior_notebook
from robot_play.env import TASKS


def test_hints_name_the_fixing_setting_and_the_generic_hint_names_none():
    assert "grip_level firm" in HINTS["stack"] and "release_height 0.14" in HINTS["bins"] and "grasp_height 0.9" in HINTS["flasks"]
    for word in ("firm", "0.14", "0.9"):
        assert word not in GENERIC_HINT                          # no answer in the placebo
    assert len(HINTS) == 3 and all(len(h.split(".")) <= 3 for h in HINTS.values())          # one sentence each


def test_hint_cells_have_no_practice_and_the_registered_size(tmp_path):
    for cell in ("hint", "hint_generic"):
        specs = build_specs(cell, ["claude-haiku-5-5", "gpt-6-luna"], list(range(20, 30)), str(tmp_path / cell))
        assert len(specs) == 2 * 3 * 10
        assert all(s.condition == cell and not s.episodes()[0]["phase"] == "practice" and len(s.episodes()) == 4 for s in specs)      # 4 held-out layouts, nothing else
    one = build_specs("hint", ["claude-haiku-5-5"], [20], str(tmp_path / "x"))
    assert {s.task: s.borrowed_notebook for s in one} == HINTS


def test_prior_cell_reads_only_existing_files_and_labels_the_text(tmp_path):
    src = tmp_path / "prior"
    src.mkdir()
    (src / "stack__s20.json").write_text(json.dumps({"text": "Try a firm grip if the cube slips."}))
    specs = build_specs("prior", ["claude-haiku-5-5"], [20, 21], str(tmp_path / "out"), source_dir=str(src))
    assert [(s.task, s.run_seed) for s in specs] == [("stack", 20)]
    assert prior_notebook(str(src), "stack", 21) == ""
    block = Memory("prior", notebook="N").prompt_block()
    assert "had read about this task but not yet attempted it" in block and block.endswith("N")


def test_prompt_labels_are_the_registered_ones():
    assert "HINT from an experienced operator" in Memory("hint", notebook="x").prompt_block()
    assert "HINT from an experienced operator" in Memory("hint_generic", notebook="x").prompt_block()
    assert Memory("hint", notebook="").prompt_block() == ""


def test_the_prior_request_contains_the_task_but_no_transcript_or_verdict():
    r = prior_request(TASKS["stack"].instruction, "- pick: moves", 20)
    assert TASKS["stack"].instruction in r and "No attempt has been made yet" in r and "verdict" in r.lower()
    assert "CURRENT NOTEBOOK" not in r
