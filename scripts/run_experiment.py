"""Run one cell of the experiment matrix (PROTOCOL.md section 5).

  python scripts/run_experiment.py --cell main --models claude-haiku-5-5 gpt-6-luna --seeds 0-4 --workers 8 --out runs/main
  python scripts/run_experiment.py --cell main --models claude-haiku-5-5 --tasks stack --seeds 0 --out runs/smoke --dry-run

`--dry-run` only prints the plan. The spend meter (runs/spend) refuses any call that could pass $90 (Anthropic) or $45 (OpenAI).
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from robot_play.runner import build_specs, run_all
from robot_play.spend import SpendMeter


def parse_seeds(s: str) -> list[int]:
    if "-" in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", required=True, choices=["main", "control", "frontier", "frontier_exp", "pilot", "pilot_pose", "pose"])
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--tasks", nargs="+", default=None)
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", required=True)
    ap.add_argument("--meter", default="runs/spend")
    ap.add_argument("--max-calls", type=int, default=None)
    ap.add_argument("--conditions", nargs="+", default=None, help="keep only these memory conditions")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    specs = build_specs(a.cell, a.models, parse_seeds(a.seeds), a.out, a.meter, a.tasks, a.max_calls)
    if a.conditions:
        specs = [s for s in specs if s.condition in a.conditions]
    n_ep = sum(len(s.episodes()) for s in specs)
    print(f"{len(specs)} runs, {n_ep} episodes, out={a.out}")
    if a.dry_run:
        for s in specs[:12]:
            print("  ", s.key, len(s.episodes()), "episodes")
        return
    t0 = time.time()
    results = run_all(specs, a.workers)
    bad = [r for r in results if r["status"] not in ("ok", "already_done")]
    print(f"finished in {(time.time() - t0) / 60:.1f} min; {len(results) - len(bad)} ok, {len(bad)} not ok")
    for r in bad:
        print("  ", r["key"], r["status"], r.get("note", ""))
    print(SpendMeter(a.meter).totals())
    raise SystemExit(0 if not bad else 3)          # the launch script retries cells that exit 3 and reports what is still not ok


if __name__ == "__main__":
    main()
