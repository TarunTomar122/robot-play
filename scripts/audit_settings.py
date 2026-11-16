"""Settings audit: change ONE tool setting at a time from its default, play the naive script, and report success per task and scene.

Why: the tools have several settings, and which of them matter differs per task. A setting that quietly solves a catch is allowed, but it has
to be known and written down, not assumed to be a harmless 'decoy'. Writes results/settings_audit.json and results/settings_audit.md.

  python scripts/audit_settings.py --seeds 20
"""
import argparse
import json
from multiprocessing import Pool
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from robot_play.scripted import run_script

OUT = Path(__file__).resolve().parents[1] / "results"
SETTINGS = [("default", {}, {}),
            ("grasp_height=0.3", {"grasp_height": 0.3}, {}), ("grasp_height=0.9", {"grasp_height": 0.9}, {}),
            ("pick speed=slow", {"speed": "slow"}, {}), ("pick speed=fast", {"speed": "fast"}, {}),
            ("grip_level=light", {"grip_level": "light"}, {}), ("grip_level=firm", {"grip_level": "firm"}, {}),
            ("yaw_offset_deg=45", {"yaw_offset_deg": 45}, {}),
            ("lift_height=0.05", {"lift_height": 0.05}, {}), ("lift_height=0.3", {"lift_height": 0.3}, {}),
            ("release_height=0", {}, {"release_height": 0.0}), ("release_height=0.14", {}, {"release_height": 0.14}), ("release_height=0.3", {}, {"release_height": 0.3}),
            ("place speed=slow", {}, {"speed": "slow"}), ("place speed=fast", {}, {"speed": "fast"}),
            ("settle_time=0", {}, {"settle_time": 0.0}), ("settle_time=1", {}, {"settle_time": 1.0})]
TASKS = ("stack", "bins", "flasks")


def one(a):
    task, quirk, si, seed = a
    try:
        r = run_script(task, seed, quirk, "naive", pick_kw=SETTINGS[si][1], place_kw=SETTINGS[si][2])
        return a, bool(r["ok"]), None
    except Exception as e:                                   # noqa: BLE001
        return a, False, f"{type(e).__name__}: {str(e)[:80]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--base", type=int, default=4000)
    ap.add_argument("--workers", type=int, default=8)
    n = ap.parse_args()
    jobs = [(t, q, si, n.base + sd) for t in TASKS for q in (True, False) for si in range(len(SETTINGS)) for sd in range(n.seeds)]
    with Pool(n.workers) as pool:
        res = pool.map(one, jobs, chunksize=4)
    table, crashes = {}, 0
    for (t, q, si, sd), ok, err in res:
        k = f"{t}|{'catch' if q else 'control'}|{SETTINGS[si][0]}"
        table[k] = table.get(k, 0) + int(ok)
        crashes += bool(err)
    (OUT / "settings_audit.json").write_text(json.dumps({"seeds": n.seeds, "base": n.base, "success": table, "crashed": crashes}, indent=1))
    lines = ["# Settings audit", "", f"The naive script, changing one setting at a time, {n.seeds} layouts per cell (seeds {n.base}+). Numbers are successes out of {n.seeds}.", "",
             "| Setting | " + " | ".join(f"{t} catch | {t} control" for t in TASKS) + " |", "|---|" + "---|" * (2 * len(TASKS))]
    for name, _, _ in SETTINGS:
        cells = [f"{table[f'{t}|{c}|{name}']}" for t in TASKS for c in ("catch", "control")]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += ["", f"Crashed runs: {crashes}"]
    (OUT / "settings_audit.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
