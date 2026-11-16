"""Gate for the pose-level toolset (no pick, no place): a script that builds pick and place from moves and the gripper must solve each catch scene when it knows the
catch, fail it with defaults, and solve the control scenes with defaults, all inside the pose-level call budget (60 calls). Writes results/gate_pose.md.

  python scripts/gate_pose.py --seeds 100
"""
import argparse, collections, json
from multiprocessing import Pool
from pathlib import Path

from robot_play.scripted import run_pose_script

OUT = Path(__file__).resolve().parents[1] / "results"


def one(a):
    task, seed, quirk, pol = a
    try:
        r = run_pose_script(task, seed, quirk, pol)
        return a, bool(r["ok"]), r["calls"], None
    except Exception as ex:                                  # noqa: BLE001
        return a, False, 0, f"{type(ex).__name__}: {str(ex)[:100]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--base", type=int, default=0)
    n = ap.parse_args()
    jobs = [(t, n.base + sd, q, p) for t in ("stack", "bins", "flasks") for q, p in ((True, "oracle"), (True, "naive"), (False, "naive")) for sd in range(n.seeds)]
    with Pool(n.workers) as pool:
        res = pool.map(one, jobs)
    agg, crashes = collections.defaultdict(lambda: {"n": 0, "ok": 0, "calls": 0}), []
    for (t, sd, q, p), ok, calls, err in res:
        a = agg[f"{t}|{'catch' if q else 'control'}|{p}"]
        a["n"] += 1
        a["ok"] += ok
        a["calls"] += calls
        if err:
            crashes.append({"task": t, "seed": sd, "quirk": q, "policy": p, "error": err})
    lines = ["# Pose-level gate", "", f"{n.seeds} layouts per row (seeds {n.base} to {n.base + n.seeds - 1}), played through `Episode` with the pose toolset and its 60-call budget.", "",
             "| Job | Scene | Policy | Success | Mean calls |", "|---|---|---|---|---|"]
    for k, a in agg.items():
        t, scene, p = k.split("|")
        lines.append(f"| {t} | {scene} | {p} | {a['ok']}/{a['n']} | {a['calls'] / a['n']:.1f} |")
    checks = []
    for t in ("stack", "bins", "flasks"):
        o, nv, c = agg[f"{t}|catch|oracle"], agg[f"{t}|catch|naive"], agg[f"{t}|control|naive"]
        checks.append((t, o["ok"] >= 0.95 * o["n"], nv["ok"] <= 0.30 * nv["n"], c["ok"] >= 0.90 * c["n"]))
    lines += ["", "Checks (oracle >= 95%, naive in the catch scene <= 30%, naive in the control scene >= 90%): " + ", ".join(f"{t}: {'PASS' if all(r) else 'FAIL ' + str(r)}" for t, *r in [(c[0], c[1], c[2], c[3]) for c in checks]),
              f"Crashed runs: {len(crashes)}"]
    (OUT / "gate_pose.md").write_text("\n".join(lines))
    (OUT / "gate_pose.json").write_text(json.dumps({"table": dict(agg), "crashes": crashes[:20]}, indent=1))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
