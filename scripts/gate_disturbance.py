"""Validation of the disturbances (PROTOCOL.md section 8): each must fire in (nearly) every episode, must break a script that does not react,
and must be recoverable by a script that re-tries. Writes results/disturbance.json and results/disturbance.md.

  python scripts/gate_disturbance.py --seeds 30
"""
import argparse, collections, json
from multiprocessing import Pool
from pathlib import Path

from robot_play.scripted import run_script

OUT = Path(__file__).resolve().parents[1] / "results"


def one(a):
    task, seed, kind, pol = a
    try:
        r = run_script(task, seed, True, pol, disturbance=kind)
        return a, bool(r["ok"]), bool(r["fired"]), None
    except Exception as ex:
        return a, False, False, f"{type(ex).__name__}: {str(ex)[:100]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--workers", type=int, default=8)
    n = ap.parse_args()
    jobs = [(t, 2000 + sd, k, p) for t in ("stack", "bins", "flasks") for k in ("slip", "nudge") for p in ("oracle", "oracle_retry") for sd in range(n.seeds)]
    with Pool(n.workers) as pool:
        res = pool.map(one, jobs)
    agg, crashes = collections.defaultdict(lambda: {"episodes": 0, "fired": 0, "success_when_fired": 0}), []
    for (t, sd, k, p), ok, fired, err in res:
        a = agg[f"{t}|{k}|{p}"]
        a["episodes"] += 1
        a["fired"] += fired
        a["success_when_fired"] += bool(ok and fired)
        if err:
            crashes.append({"task": t, "seed": sd, "kind": k, "policy": p, "error": err})
    checks = {}
    for t in ("stack", "bins", "flasks"):
        for k in ("slip", "nudge"):
            r, rr = agg[f"{t}|{k}|oracle"], agg[f"{t}|{k}|oracle_retry"]
            checks[f"{t}|{k}"] = {"fires_in_>=95%": rr["fired"] >= 0.95 * rr["episodes"],
                                  "breaks_no_reaction_script(<=30%)": r["success_when_fired"] <= 0.30 * max(r["fired"], 1),
                                  "recoverable_by_retry(>=80%)": rr["success_when_fired"] >= 0.80 * max(rr["fired"], 1)}
    (OUT / "disturbance.json").write_text(json.dumps({"seeds": n.seeds, "table": dict(agg), "checks": checks, "crashes": crashes}, indent=1))
    lines = ["# Disturbance validation", "", f"{n.seeds} episodes per row (seeds 2000+), catch scenes. 'No reaction' = the script that knows the catch but never retries.", "",
             "| Job | Disturbance | Fired | Success, no reaction | Success, retries |", "|---|---|---|---|---|"]
    for t in ("stack", "bins", "flasks"):
        for k in ("slip", "nudge"):
            r, rr = agg[f"{t}|{k}|oracle"], agg[f"{t}|{k}|oracle_retry"]
            lines.append(f"| {t} | {k} | {rr['fired']}/{rr['episodes']} | {r['success_when_fired']}/{r['fired']} | {rr['success_when_fired']}/{rr['fired']} |")
    lines += ["", "Checks: " + ", ".join(f"{k}: {'PASS' if all(v.values()) else 'FAIL'}" for k, v in checks.items()), f"Crashed runs: {len(crashes)}"]
    (OUT / "disturbance.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
