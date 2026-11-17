"""scripts/check_run_files.py: what it accepts and what it refuses."""
import json
import subprocess
import sys
from pathlib import Path

from robot_play.runner import GENERIC_HINT

CHECK = str(Path(__file__).resolve().parents[1] / "scripts" / "check_run_files.py")


def header(run_seed=20, condition="lm_generic", code="a" * 16, text=GENERIC_HINT, n=2, task="stack"):
    plan = [{"phase": "eval", "idx": j, "seed": 20000 + 100 * run_seed + j, "disturbance": None} for j in range(n)]
    return {"_config": {"model": "m", "task": task, "condition": condition, "run_seed": run_seed, "quirk": True, "toolset": "skills", "plan": plan, "code": code, "borrowed_notebook": text}}


def row(cfg, j, **over):
    c = cfg["_config"]
    r = {"run": f"{c['model']}__{c['task']}__{c['condition']}__quirk__p0__s{c['run_seed']}", "model": c["model"], "task": c["task"], "condition": c["condition"], "quirk": True, "run_seed": c["run_seed"],
         "phase": "eval", "idx": j, "seed": 20000 + 100 * c["run_seed"] + j, "toolset": "skills", "result": {"seed": 20000 + 100 * c["run_seed"] + j, "success": True},
         "memory": {"notebook": c["borrowed_notebook"], "replay": ""}}
    r.update(over)
    return r


def write(folder, cfg, rows, stem=None):
    folder.mkdir(parents=True, exist_ok=True)
    c = cfg["_config"]
    f = folder / ((stem or f"m__{c['task']}__{c['condition']}__quirk__p0__s{c['run_seed']}") + ".jsonl")
    f.write_text("\n".join(json.dumps(x) for x in [cfg, *rows]) + "\n")
    return f


def check(folder, *flags):
    p = subprocess.run([sys.executable, CHECK, *flags, str(folder)], capture_output=True, text=True)
    return p.returncode, p.stdout


def test_a_clean_file_passes(tmp_path):
    cfg = header()
    write(tmp_path / "a", cfg, [row(cfg, 0), row(cfg, 1)])
    assert check(tmp_path / "a")[0] == 0


def test_empty_headerless_and_missing_things_fail(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.jsonl").write_text("")
    assert check(tmp_path / "a")[0] == 1                                    # empty file
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "x.jsonl").write_text('{"run": "no header"}\n')
    assert check(tmp_path / "b")[0] == 1                                    # no header
    assert check(tmp_path / "nowhere")[0] == 1                              # no such folder
    (tmp_path / "c").mkdir()
    assert check(tmp_path / "c")[0] == 1                                    # not one run file


def test_plan_seed_that_breaks_the_rule_fails(tmp_path):
    cfg = header()
    cfg["_config"]["plan"][1]["seed"] = 99999
    write(tmp_path / "a", cfg, [row(cfg, 0)])
    code, out = check(tmp_path / "a")
    assert code == 1 and "registered" in out


def test_a_row_that_disagrees_with_its_header_or_repeats_fails(tmp_path):
    cfg = header()
    write(tmp_path / "a", cfg, [row(cfg, 0), row(cfg, 1, condition="none")])
    assert check(tmp_path / "a")[0] == 1                                    # wrong condition
    write(tmp_path / "b", cfg, [row(cfg, 0), row(cfg, 0)])
    assert check(tmp_path / "b")[0] == 1                                    # repeated episode
    write(tmp_path / "c", cfg, [row(cfg, 0, seed=1)])
    assert check(tmp_path / "c")[0] == 1                                    # wrong seed
    write(tmp_path / "d", cfg, [row(cfg, 0, run="other")])
    assert check(tmp_path / "d")[0] == 1                                    # wrong run name


def test_code_hash_is_checked_only_against_the_expected_ones(tmp_path):
    cfg = header(code="b" * 16)
    write(tmp_path / "a", cfg, [row(cfg, 0), row(cfg, 1)])
    assert check(tmp_path / "a")[0] == 0
    assert check(tmp_path / "a", "--expect", "b" * 16)[0] == 0
    assert check(tmp_path / "a", "--expect", "c" * 16)[0] == 1


def test_a_changed_registered_memory_text_fails(tmp_path):
    cfg = header(text=GENERIC_HINT + " Extra.")
    write(tmp_path / "a", cfg, [row(cfg, 0), row(cfg, 1)])
    code, out = check(tmp_path / "a")
    assert code == 1 and "registered text" in out


def test_an_episode_whose_memory_differs_from_the_header_fails(tmp_path):
    cfg = header()
    write(tmp_path / "a", cfg, [row(cfg, 0), row(cfg, 1, memory={"notebook": GENERIC_HINT + " Extra.", "replay": ""})])
    code, out = check(tmp_path / "a")
    assert code == 1 and "memory that differs" in out


def test_a_run_seed_outside_the_folders_range_fails(tmp_path):
    cfg = header(run_seed=35)                                               # wordsplit holds run seeds 20 to 29
    write(tmp_path / "wordsplit", cfg, [row(cfg, 0), row(cfg, 1)])
    code, out = check(tmp_path / "wordsplit")
    assert code == 1 and "outside the folder's range" in out
    cfg2 = header(run_seed=25)
    write(tmp_path / "wordsplit2", cfg2, [row(cfg2, 0), row(cfg2, 1)])      # wordsplit2 holds 30 to 39
    assert check(tmp_path / "wordsplit2")[0] == 1
    write(tmp_path / "other_folder", cfg2, [row(cfg2, 0), row(cfg2, 1)])    # an unknown folder has no range
    assert check(tmp_path / "other_folder")[0] == 0


def test_a_failed_import_of_the_registered_texts_is_a_failure_not_a_skip(tmp_path):
    cfg = header()
    write(tmp_path / "a", cfg, [row(cfg, 0), row(cfg, 1)])
    stub = tmp_path / "stub"
    (stub / "robot_play").mkdir(parents=True)
    (stub / "robot_play" / "__init__.py").write_text("")
    (stub / "robot_play" / "runner.py").write_text("raise ImportError('simulated')\n")
    env = {"PYTHONPATH": str(stub), "PATH": "/usr/bin:/bin"}
    p = subprocess.run([sys.executable, "-S", CHECK, str(tmp_path / "a")], capture_output=True, text=True, env=env)
    assert p.returncode == 1 and "cannot import robot_play.runner" in p.stdout
